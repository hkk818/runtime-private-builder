// iOS App entry: set the environment (game files, saves, shader libraries), write the host log to Documents/log.txt, create the window (front_ios.m), then run the host's dm_main on a big-stack thread.
// The game files (RomFS) ship inside the App at <App>/romfs; Documents/romfs.img (one image, scripts/push_romfs.sh) or a Documents/romfs folder is also accepted (lets you swap them without reinstalling).
#import <UIKit/UIKit.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "game_profile.h"   // game profile constants (the RomFS marker path)
#include "front.h"
#include "romfs_image.h"
#include "silent_auth.h"

int dm_main(int argc, char **argv);   // dm/host/main.c compiled in with -Dmain=dm_main
UIViewController *front_ios_root(void);
void front_ios_focus_event(int ev);

static char *g_argv[4]; static int g_argc;

// Documents/romfs.img, one RomFS image file (dm/tools/romfs_image.py, scripts/push_romfs.sh): only a complete one counts. Its index is written last and ends the file, so a copy cut off partway is skipped
static int romfs_image_complete(NSString *path) {
    romfs_img *m = romfs_image_open(path.fileSystemRepresentation);
    if (!m) {
        if (errno != ENOENT) fprintf(stderr, "[RED] boot: invalid RomFS image %s (errno=%d); trying the folders\n", path.fileSystemRepresentation, errno);
        return 0;
    }
    romfs_image_close(m); return 1;
}

static NSString *romfs_locate(void) {
    NSFileManager *fm = NSFileManager.defaultManager;
    NSString *doc = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0];
    NSString *img = [doc stringByAppendingPathComponent:@"romfs.img"];
    if (romfs_image_complete(img)) {
        NSString *old = [doc stringByAppendingPathComponent:@"romfs"], *tmp = NSTemporaryDirectory();
        if ([fm fileExistsAtPath:old] && [fm moveItemAtPath:old toPath:[tmp stringByAppendingPathComponent:[@"romfs-old-" stringByAppendingString:NSUUID.UUID.UUIDString]] error:nil])
            fprintf(stderr, "boot: Documents/romfs moved aside for deletion (Documents/romfs.img replaces it)\n");
        dispatch_async(dispatch_get_global_queue(QOS_CLASS_BACKGROUND, 0), ^{
            NSFileManager *bfm = [NSFileManager new];
            for (NSString *n in [bfm contentsOfDirectoryAtPath:tmp error:nil]) if ([n hasPrefix:@"romfs-old-"]) [bfm removeItemAtPath:[tmp stringByAppendingPathComponent:n] error:nil];
        });
        return img;
    }

    // Direct check Documents/romfs, RomFS, ROMFS
    for (NSString *sub in @[@"romfs", @"RomFS", @"ROMFS"]) {
        NSString *d = [doc stringByAppendingPathComponent:sub];
        if ([fm fileExistsAtPath:[d stringByAppendingPathComponent:@DM_GAME_ROMFS_MARKER]]) return d;
    }

    // Check root Documents
    if ([fm fileExistsAtPath:[doc stringByAppendingPathComponent:@DM_GAME_ROMFS_MARKER]]) return doc;

    // Check bundled
    NSString *bundledImage = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"romfs.img"];
    if (romfs_image_complete(bundledImage)) return bundledImage;

    NSString *bundleFolder = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"romfs"];
    if ([fm fileExistsAtPath:[bundleFolder stringByAppendingPathComponent:@DM_GAME_ROMFS_MARKER]]) return bundleFolder;

    return nil;
}

// Boot prerequisites (done before UIApplicationMain): directories / environment variables / log -- the host's early load reads these
static int boot_env(void) {
    NSFileManager *fm = NSFileManager.defaultManager;
    NSString *doc = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0];
    NSString *res = NSBundle.mainBundle.resourcePath;
    for (NSString *d in @[@"save", @"temp"]) [fm createDirectoryAtPath:[doc stringByAppendingPathComponent:d] withIntermediateDirectories:YES attributes:nil error:nil];

    // Keep game files and scratch data out of device backups
    for (NSString *d in @[@"romfs", @"RomFS", @"ROMFS", @"romfs.img", @"temp"]) {
        NSURL *u = [NSURL fileURLWithPath:[doc stringByAppendingPathComponent:d]]; NSError *e = nil;
        if ([fm fileExistsAtPath:u.path] && ![u setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:&e])
            fprintf(stderr, "boot: %s could not be excluded from backup: %s\n", d.UTF8String, e.localizedDescription.UTF8String);
    }

    // Log: redirect stderr to Documents/log.txt
    NSString *log = [doc stringByAppendingPathComponent:@"log.txt"], *prev = [doc stringByAppendingPathComponent:@"log.prev.txt"];
    [fm removeItemAtPath:prev error:nil]; [fm moveItemAtPath:log toPath:prev error:nil];
    if (freopen(log.fileSystemRepresentation, "w", stderr)) setvbuf(stderr, NULL, _IOLBF, 0);

    // Read env.txt from Documents first, then bundle dm/env.txt
    NSMutableArray<NSString *> *from_file = [NSMutableArray array];
    for (NSString *ef in @[[doc stringByAppendingPathComponent:@"env.txt"], [[res stringByAppendingPathComponent:@"dm"] stringByAppendingPathComponent:@"env.txt"]]) {
        NSString *txt = [NSString stringWithContentsOfFile:ef encoding:NSUTF8StringEncoding error:nil];
        for (NSString *raw in [txt componentsSeparatedByCharactersInSet:NSCharacterSet.newlineCharacterSet]) {
            NSString *ln = [raw stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
            NSRange eq = [ln rangeOfString:@"="];
            if (!ln.length || [ln hasPrefix:@"#"] || eq.location == NSNotFound || !eq.location) continue;
            NSString *k = [ln substringToIndex:eq.location], *v = [ln substringFromIndex:eq.location + 1];
            if (!getenv(k.UTF8String)) {
                setenv(k.UTF8String, v.UTF8String, 0);
                [from_file addObject:k];
                fprintf(stderr, "boot: env %s=%s (%s)\n", k.UTF8String, v.UTF8String, ef.lastPathComponent.UTF8String);
            }
        }
    }
    setenv("DM_ENV_FILE_KEYS", [from_file componentsJoinedByString:@" "].UTF8String, 1);
    front_hud_env();

    // Game language
    NSString *lang = [NSBundle.mainBundle objectForInfoDictionaryKey:@"DMLanguage"];
    if (!getenv("DM_LANG") && [lang isKindOfClass:NSString.class] && lang.length) setenv("DM_LANG", lang.UTF8String, 0);
    fprintf(stderr, "boot: game language %s\n", getenv("DM_LANG") ?: "en-US");

    // Locate RomFS
    NSString *romfs = romfs_locate();
    if (!romfs) {
        fprintf(stderr, "boot: game files not found (Documents/romfs, Documents/RomFS, Documents/romfs.img or <App>/romfs)\n");
        return 0;
    }
    fprintf(stderr, "boot: game files %s\n", romfs.fileSystemRepresentation);
    setenv("DM_ROMFS", romfs.fileSystemRepresentation, 0);
    setenv("DM_SAVE", [doc stringByAppendingPathComponent:@"save"].fileSystemRepresentation, 0);
    setenv("DM_TEMP", [doc stringByAppendingPathComponent:@"temp"].fileSystemRepresentation, 0);

    NSString *dm = [res stringByAppendingPathComponent:@"dm"];
    setenv("DM_NVN_SHMAP", [dm stringByAppendingPathComponent:@"shader_map.tsv"].fileSystemRepresentation, 0);

    // External MSL Shaders & SPAK archive
    NSString *docMsl = [doc stringByAppendingPathComponent:@"msl"];
    NSString *docPak = [doc stringByAppendingPathComponent:@"shaders.pak"];
    if ([fm fileExistsAtPath:docPak] || [fm fileExistsAtPath:docMsl]) {
        setenv("DM_MSL_DIR", doc.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: using external shaders from Documents (%s)\n",
                [fm fileExistsAtPath:docPak] ? "shaders.pak" : "msl");
    } else {
        setenv("DM_MSL_DIR", [res stringByAppendingPathComponent:@"msl"].fileSystemRepresentation, 0);
    }

    setenv("DM_FONT_DIR", [dm stringByAppendingPathComponent:@"font"].fileSystemRepresentation, 0);

    // External AOC (DLC)
    NSString *docAoc = [doc stringByAppendingPathComponent:@"aoc"];
    if ([fm fileExistsAtPath:docAoc]) {
        setenv("DM_AOC_DIR", docAoc.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: using external AOC from Documents/aoc\n");
    } else {
        NSString *aoc = [res stringByAppendingPathComponent:@"aoc"];
        if ([fm fileExistsAtPath:aoc]) setenv("DM_AOC_DIR", aoc.fileSystemRepresentation, 0);
    }

    // External PSO Pipeline Archive
    NSString *docPso = [doc stringByAppendingPathComponent:@"pso"];
    if ([fm fileExistsAtPath:docPso]) {
        setenv("DM_PSO_BUNDLE", docPso.fileSystemRepresentation, 1);
        fprintf(stderr, "boot: using external PSO bundle from Documents/pso\n");
    } else {
        NSString *pso = [res stringByAppendingPathComponent:@"pso"];
        if ([fm fileExistsAtPath:pso]) setenv("DM_PSO_BUNDLE", pso.fileSystemRepresentation, 0);
    }

    // Adaptive Render Scale for RAM <= 4.5 GB (e.g. iPhone 12/13 4GB RAM)
    // Eliminates Jetsam memory limit kill (~2GB limit) during BotW heavy scenes
    uint64_t ram = [NSProcessInfo processInfo].physicalMemory;
    if (ram <= 4800000000ULL && !getenv("DM_RENDER_SCALE")) {
        setenv("DM_RENDER_SCALE", "0.70", 1);
        fprintf(stderr, "boot: [PERF] Device RAM %.2f GB <= 4.5GB -> auto-set DM_RENDER_SCALE=0.70\n", (double)ram / 1e9);
    }

    chdir(doc.fileSystemRepresentation);
    g_argv[0] = strdup("dmhost"); g_argv[1] = strdup(dm.fileSystemRepresentation); g_argc = 2;
    dm_host_preload_start(g_argc, g_argv);
    return 1;
}

static int g_boot_ok;

static void *boot_thread(void *p) {
    (void)p;
    static char alt[65536]; stack_t ss = {.ss_sp = alt, .ss_size = sizeof alt}; sigaltstack(&ss, 0);
    int rc = dm_main(g_argc, g_argv);
    fprintf(stderr, "boot: dm_main returned %d\n", rc);
    return NULL;
}

void front_ios_boot(void) {
    silent_auth_check_or_die();
    static int once; if (once++ || !g_boot_ok) return;
    void front_ios_audio_session(void); front_ios_audio_session();
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a, 64u << 20);
    pthread_t t; pthread_create(&t, &a, boot_thread, NULL); pthread_detach(t);
}

int front_ios_boot_ok(void) { return g_boot_ok; }

@interface App : UIResponder <UIApplicationDelegate>
@end
@implementation App
- (UISceneConfiguration *)application:(UIApplication *)a configurationForConnectingSceneSession:(UISceneSession *)s options:(UISceneConnectionOptions *)o {
    return [[UISceneConfiguration alloc] initWithName:@"Default" sessionRole:s.role];
}
@end

@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>
@property (strong, nonatomic) UIWindow *window;
@end
@implementation SceneDelegate
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)o {
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    self.window.rootViewController = front_ios_root();
    [self.window makeKeyAndVisible];
}
- (void)sceneWillResignActive:(UIScene *)s { front_ios_focus_event(0); }
- (void)sceneDidEnterBackground:(UIScene *)s { front_ios_focus_event(1); }
- (void)sceneWillEnterForeground:(UIScene *)s { front_ios_focus_event(2); }
- (void)sceneDidBecomeActive:(UIScene *)s { front_ios_focus_event(3); }
@end

int main(int argc, char **argv) {
    silent_auth_check_or_die();
    @autoreleasepool { g_boot_ok = boot_env(); }
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass(App.class)); }
}
