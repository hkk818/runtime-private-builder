
#import <UIKit/UIKit.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>
#import <AVFAudio/AVFAudio.h>
#import <objc/runtime.h>
#include <stdint.h>
#include <errno.h>
#include "front.h"
#include "hle.h"
#include "dm.h"
#include "haptics_apple.h"

// ---- BOTW Master HUD & Cheats & Macro Overlay ----
void dm_macro_trigger_windbomb(void);
void dm_macro_toggle_whistling(BOOL enable);
void dm_macro_trigger_parry(void);
void dm_turbo_set(BOOL a, BOOL y);
void dm_gamepad_set_edit_mode(BOOL edit);
BOOL dm_gamepad_is_edit_mode(void);
void dm_gamepad_reset_layout(void);
void dm_gamepad_save_layout(void);
extern uint8_t *dm_fps_state;

@interface DmMasterHUD : UIView
@property (nonatomic, strong) UISwitch *swHealth;
@property (nonatomic, strong) UISwitch *swStamina;
@property (nonatomic, strong) UISwitch *swDurability;
@property (nonatomic, strong) UISwitch *swArrows;
@property (nonatomic, strong) UISwitch *swWhistle;
@property (nonatomic, strong) UISwitch *swTurboA;
@property (nonatomic, strong) UISwitch *swTurboY;
@property (nonatomic, strong) UISlider *sldSize;
@property (nonatomic, strong) UISlider *sldOpacity;
@end

@implementation DmMasterHUD
- (instancetype)initWithFrame:(CGRect)frame {
    if ((self = [super initWithFrame:frame])) {
        self.backgroundColor = [UIColor colorWithWhite:0.1 alpha:0.88];
        self.layer.cornerRadius = 16;
        self.layer.borderWidth = 1.5;
        self.layer.borderColor = [UIColor colorWithWhite:0.35 alpha:0.9].CGColor;
        self.clipsToBounds = YES;

        UIScrollView *sc = [[UIScrollView alloc] initWithFrame:self.bounds];
        sc.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        [self addSubview:sc];

        CGFloat y = 14;
        UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(20, y, frame.size.width - 40, 26)];
        title.text = @"BOTW 旷野之息 战术增强控制台 (Master HUD)";
        title.textColor = [UIColor colorWithRed:0.2 green:0.8 blue:1.0 alpha:1.0];
        title.font = [UIFont boldSystemFontOfSize:17];
        title.textAlignment = NSTextAlignmentCenter;
        [sc addSubview:title];
        y += 34;

        // --- Cheats Section ---
        UILabel *secCheats = [[UILabel alloc] initWithFrame:CGRectMake(20, y, 200, 20)];
        secCheats.text = @"【 双模金手指 (Cheats) 】";
        secCheats.textColor = UIColor.yellowColor;
        secCheats.font = [UIFont boldSystemFontOfSize:14];
        [sc addSubview:secCheats];
        y += 24;

        self.swHealth = [self addToggle:sc title:@"锁血 / 无限生命 (Invincible)" y:&y key:@"DM_CHEAT_HEALTH"];
        self.swStamina = [self addToggle:sc title:@"无限精力 / 体力 (Infinite Stamina)" y:&y key:@"DM_CHEAT_STAMINA"];
        self.swDurability = [self addToggle:sc title:@"武器防具不磨损 (Unbreakable)" y:&y key:@"DM_CHEAT_DURABILITY"];
        self.swArrows = [self addToggle:sc title:@"无限箭矢 (Infinite Arrows)" y:&y key:@"DM_CHEAT_ARROWS"];

        y += 8;
        // --- Macros Section ---
        UILabel *secMacro = [[UILabel alloc] initWithFrame:CGRectMake(20, y, 200, 20)];
        secMacro.text = @"【 战术动作宏与特技 (Macros) 】";
        secMacro.textColor = UIColor.cyanColor;
        secMacro.font = [UIFont boldSystemFontOfSize:14];
        [sc addSubview:secMacro];
        y += 24;

        UIButton *btnWindbomb = [self addButton:sc title:@"🚀 一键风弹起飞 (Windbomb Blast Off)" y:&y action:@selector(actWindbomb)];
        btnWindbomb.backgroundColor = [UIColor colorWithRed:0.1 green:0.4 blue:0.7 alpha:0.8];

        UIButton *btnParry = [self addButton:sc title:@"🛡️ 完美盾反时机 (Shield Parry Assist)" y:&y action:@selector(actParry)];
        btnParry.backgroundColor = [UIColor colorWithRed:0.2 green:0.5 blue:0.3 alpha:0.8];

        self.swWhistle = [self addToggle:sc title:@"无限吹哨狂奔 (Whistling Sprint)" y:&y key:nil];
        [self.swWhistle addTarget:self action:@selector(actWhistle:) forControlEvents:UIControlEventValueChanged];

        self.swTurboA = [self addToggle:sc title:@"Turbo A 极速拾取 (15Hz Auto A)" y:&y key:nil];
        [self.swTurboA addTarget:self action:@selector(actTurbo:) forControlEvents:UIControlEventValueChanged];

        self.swTurboY = [self addToggle:sc title:@"Turbo Y 连续近战普攻 (15Hz Auto Y)" y:&y key:nil];
        [self.swTurboY addTarget:self action:@selector(actTurbo:) forControlEvents:UIControlEventValueChanged];

        y += 8;
        // --- Controls Section ---
        UILabel *secCtrl = [[UILabel alloc] initWithFrame:CGRectMake(20, y, 200, 20)];
        secCtrl.text = @"【 触控按键个性化 (Controls) 】";
        secCtrl.textColor = UIColor.orangeColor;
        secCtrl.font = [UIFont boldSystemFontOfSize:14];
        [sc addSubview:secCtrl];
        y += 24;

        UILabel *lblSz = [[UILabel alloc] initWithFrame:CGRectMake(20, y, 160, 20)];
        lblSz.text = @"按键尺寸 (60%~140%):";
        lblSz.textColor = UIColor.whiteColor; lblSz.font = [UIFont systemFontOfSize:13];
        [sc addSubview:lblSz];
        self.sldSize = [[UISlider alloc] initWithFrame:CGRectMake(180, y, frame.size.width - 200, 20)];
        self.sldSize.minimumValue = 0.6f; self.sldSize.maximumValue = 1.4f;
        float curSz = [[NSUserDefaults standardUserDefaults] floatForKey:@"MNGTouchButtonSize"];
        self.sldSize.value = (curSz >= 0.6f && curSz <= 1.4f) ? curSz : 1.0f;
        [self.sldSize addTarget:self action:@selector(actSize:) forControlEvents:UIControlEventValueChanged];
        [sc addSubview:self.sldSize];
        y += 28;

        UILabel *lblOp = [[UILabel alloc] initWithFrame:CGRectMake(20, y, 160, 20)];
        lblOp.text = @"按键透明度 (10%~100%):";
        lblOp.textColor = UIColor.whiteColor; lblOp.font = [UIFont systemFontOfSize:13];
        [sc addSubview:lblOp];
        self.sldOpacity = [[UISlider alloc] initWithFrame:CGRectMake(180, y, frame.size.width - 200, 20)];
        self.sldOpacity.minimumValue = 0.1f; self.sldOpacity.maximumValue = 1.0f;
        float curOp = [[NSUserDefaults standardUserDefaults] floatForKey:@"MNGTouchOpacity"];
        self.sldOpacity.value = (curOp >= 0.1f && curOp <= 1.0f) ? curOp : 0.5f;
        [self.sldOpacity addTarget:self action:@selector(actOpacity:) forControlEvents:UIControlEventValueChanged];
        [sc addSubview:self.sldOpacity];
        y += 32;

        UIButton *btnEdit = [self addButton:sc title:@"🎨 进入全自由拖拽手柄编辑模式" y:&y action:@selector(actEditLayout)];
        btnEdit.backgroundColor = [UIColor colorWithRed:0.7 green:0.3 blue:0.1 alpha:0.85];

        UIButton *btnSave = [self addButton:sc title:@"💾 保存手柄布局并退出编辑" y:&y action:@selector(actSaveLayout)];
        btnSave.backgroundColor = [UIColor colorWithRed:0.2 green:0.6 blue:0.2 alpha:0.85];

        UIButton *btnReset = [self addButton:sc title:@"🔄 重置手柄默认布局" y:&y action:@selector(actResetLayout)];
        btnReset.backgroundColor = [UIColor colorWithRed:0.5 green:0.2 blue:0.2 alpha:0.85];

        y += 10;
        UIButton *btnClose = [self addButton:sc title:@"✖️ 关闭控制台 (Resume Game)" y:&y action:@selector(actClose)];
        btnClose.backgroundColor = [UIColor colorWithWhite:0.2 alpha:0.9];
        y += 20;

        sc.contentSize = CGSizeMake(frame.size.width, y);
    }
    return self;
}

- (UISwitch *)addToggle:(UIScrollView *)sc title:(NSString *)title y:(CGFloat *)y key:(NSString *)key {
    UILabel *lbl = [[UILabel alloc] initWithFrame:CGRectMake(20, *y + 4, self.bounds.size.width - 90, 24)];
    lbl.text = title; lbl.textColor = UIColor.whiteColor; lbl.font = [UIFont systemFontOfSize:13];
    [sc addSubview:lbl];
    UISwitch *sw = [[UISwitch alloc] initWithFrame:CGRectMake(self.bounds.size.width - 70, *y, 50, 24)];
    if (key) {
        sw.on = [[NSUserDefaults standardUserDefaults] boolForKey:key];
        objc_setAssociatedObject(sw, "KEY", key, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        [sw addTarget:self action:@selector(actCheatToggle:) forControlEvents:UIControlEventValueChanged];
    }
    [sc addSubview:sw];
    *y += 34;
    return sw;
}

- (UIButton *)addButton:(UIScrollView *)sc title:(NSString *)title y:(CGFloat *)y action:(SEL)act {
    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(20, *y, self.bounds.size.width - 40, 32);
    [btn setTitle:title forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    btn.layer.cornerRadius = 8;
    [btn addTarget:self action:act forControlEvents:UIControlEventTouchUpInside];
    [sc addSubview:btn];
    *y += 38;
    return btn;
}

- (void)actCheatToggle:(UISwitch *)sw {
    NSString *key = objc_getAssociatedObject(sw, "KEY");
    if (key) {
        [[NSUserDefaults standardUserDefaults] setBool:sw.on forKey:key];
        [[NSUserDefaults standardUserDefaults] synchronize];
        if (dm_fps_state) {
            uint8_t mask = 0;
            if ([[NSUserDefaults standardUserDefaults] boolForKey:@"DM_CHEAT_HEALTH"]) mask |= 1;
            if ([[NSUserDefaults standardUserDefaults] boolForKey:@"DM_CHEAT_STAMINA"]) mask |= 2;
            if ([[NSUserDefaults standardUserDefaults] boolForKey:@"DM_CHEAT_DURABILITY"]) mask |= 4;
            if ([[NSUserDefaults standardUserDefaults] boolForKey:@"DM_CHEAT_ARROWS"]) mask |= 8;
            dm_fps_state[0x20] = mask;
        }
    }
}

- (void)actWhistle:(UISwitch *)sw { dm_macro_toggle_whistling(sw.on); }
- (void)actTurbo:(UISwitch *)sw { dm_turbo_set(self.swTurboA.on, self.swTurboY.on); }
- (void)actWindbomb { self.hidden = YES; dm_macro_trigger_windbomb(); }
- (void)actParry { dm_macro_trigger_parry(); }
- (void)actSize:(UISlider *)sld {
    [[NSUserDefaults standardUserDefaults] setFloat:sld.value forKey:@"MNGTouchButtonSize"];
    [[NSUserDefaults standardUserDefaults] synchronize];
}
- (void)actOpacity:(UISlider *)sld {
    [[NSUserDefaults standardUserDefaults] setFloat:sld.value forKey:@"MNGTouchOpacity"];
    [[NSUserDefaults standardUserDefaults] synchronize];
}
- (void)actEditLayout {
    self.hidden = YES;
    dm_gamepad_set_edit_mode(YES);
}
- (void)actSaveLayout {
    dm_gamepad_save_layout();
    dm_gamepad_set_edit_mode(NO);
}
- (void)actResetLayout {
    dm_gamepad_reset_layout();
    dm_gamepad_set_edit_mode(NO);
}
- (void)actClose { self.hidden = YES; }
@end
// iOS front end (the iOS implementation of front.h): a centered 16:9 Metal view (black bars on both sides) + a full-screen virtual gamepad layer (DmGamepad.m, controls drawn over the picture).
// The host runs on the big-stack thread started by main.m; front_run runs the guest directly on the calling thread.
#import <UIKit/UIKit.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>
#import <AVFAudio/AVFAudio.h>
#include <errno.h>
#include "front.h"
#include "hle.h"
#include "dm.h"
#include "haptics_apple.h"

UIView *dm_gamepad_view(CGRect frame);
void dm_gamepad_reset(void);
void front_ios_boot(void);
int front_ios_boot_ok(void);
const char *front_ios_boot_message(void);   // main.m: why a build that keeps the game files off the IPA found none usable (NULL = the generic hint)
bool dm_show_launcher(void *view_controller, void (*done)(void));   // Launcher.swift: false = no launcher (no dm/launcher.json, or DM_LAUNCHER=0)

static CAMetalLayer *g_layer;
static void front_ios_power_watch(void);
static void front_ios_audio_watch(void);
static UILabel *front_ios_fps_label(void);

@interface DmGameView : UIView
@end
@implementation DmGameView
+ (Class)layerClass { return CAMetalLayer.class; }
- (instancetype)initWithFrame:(CGRect)f {
    if ((self = [super initWithFrame:f])) {
        CAMetalLayer *l = (CAMetalLayer *)self.layer;
        l.device = MTLCreateSystemDefaultDevice(); l.pixelFormat = MTLPixelFormatBGRA8Unorm;
        l.contentsScale = UIScreen.mainScreen.nativeScale; l.framebufferOnly = NO; l.opaque = YES;
        self.backgroundColor = UIColor.blackColor;
    }
    return self;
}
- (void)layoutSubviews {
    [super layoutSubviews];
    CAMetalLayer *l = (CAMetalLayer *)self.layer;
    l.drawableSize = CGSizeMake(self.bounds.size.width * l.contentsScale, self.bounds.size.height * l.contentsScale);
}
@end

@interface DmRootVC : UIViewController
@property (nonatomic, strong) DmGameView *game;
@property (nonatomic, strong) UIView *pad;
@property (nonatomic, strong) UILabel *fps;
@property (nonatomic, strong) DmMasterHUD *hud;
@property (nonatomic, strong) UIButton *btnHUD;
@property (nonatomic) BOOL launched;
- (void)startGame;
@end
static DmRootVC *g_root;
static void launcher_done(void) { [g_root startGame]; }
@implementation DmRootVC
- (void)toggleHUD {
    self.hud.hidden = !self.hud.hidden;
    if (!self.hud.hidden) [self.view bringSubviewToFront:self.hud];
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = UIColor.blackColor;
    front_ios_power_watch();
    if (!front_ios_boot_ok()) {   // No game files: show a hint and do not start the host
        UILabel *lb = [[UILabel alloc] initWithFrame:CGRectInset(self.view.bounds, 40, 40)];
        lb.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        lb.numberOfLines = 0; lb.textAlignment = NSTextAlignmentCenter; lb.textColor = UIColor.whiteColor;
        const char *why = front_ios_boot_message();
        lb.text = why ? [NSString stringWithFormat:@"Game files unusable.\n%s", why] : @"Game files not found.\nPut the RomFS folder into this App's Documents as \"romfs\" (Files app), then restart.";
        [self.view addSubview:lb]; return;
    }
    front_ios_audio_watch();
}
// The game view, the pad and the frame-rate counter are made once the launcher has set the switches they read (DM_SHOW_FPS, DM_METAL_HUD); the host's loading began at app launch (main.m)
- (void)startGame {
    if (self.game) return;
    front_hud_env();   // before the game view makes its device (an env file's DM_METAL_HUD sets it in main.m already)
    self.game = [[DmGameView alloc] initWithFrame:self.view.bounds];
    [self.view addSubview:self.game];
    g_layer = (CAMetalLayer *)self.game.layer;
    if (getenv("DM_METAL_HUD") && atoi(getenv("DM_METAL_HUD"))) { g_layer.developerHUDProperties = @{@"mode": @"default"}; LOG("front end: Metal performance HUD on (DM_METAL_HUD)"); }   // Apple's HUD over the game: frame rate, frame and GPU time, memory
    dm_haptics_apple_init();
    self.pad = dm_gamepad_view(self.view.bounds);
    self.pad.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.view addSubview:self.pad];

    // Master HUD overlay
    CGFloat hudW = MIN(self.view.bounds.size.width - 60, 480.0);
    CGFloat hudH = MIN(self.view.bounds.size.height - 40, 360.0);
    self.hud = [[DmMasterHUD alloc] initWithFrame:CGRectMake((self.view.bounds.size.width - hudW) / 2, (self.view.bounds.size.height - hudH) / 2, hudW, hudH)];
    self.hud.hidden = YES;
    [self.view addSubview:self.hud];

    // Floating pill button to toggle HUD
    self.btnHUD = [UIButton buttonWithType:UIButtonTypeCustom];
    self.btnHUD.frame = CGRectMake(self.view.bounds.size.width - 64, 8, 48, 26);
    [self.btnHUD setTitle:@"HUD" forState:UIControlStateNormal];
    [self.btnHUD setTitleColor:UIColor.cyanColor forState:UIControlStateNormal];
    self.btnHUD.titleLabel.font = [UIFont boldSystemFontOfSize:11];
    self.btnHUD.backgroundColor = [UIColor colorWithWhite:0.1 alpha:0.65];
    self.btnHUD.layer.cornerRadius = 13;
    self.btnHUD.layer.borderWidth = 1.0;
    self.btnHUD.layer.borderColor = [UIColor colorWithWhite:0.4 alpha:0.8].CGColor;
    [self.btnHUD addTarget:self action:@selector(toggleHUD) forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:self.btnHUD];

    // Double tap top gesture or 3-finger tap gesture
    UITapGestureRecognizer *tripleTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(toggleHUD)];
    tripleTap.numberOfTouchesRequired = 3;
    [self.view addGestureRecognizer:tripleTap];
    self.fps = front_ios_fps_label();   // above the pad, which hides while a controller is connected
    if (self.fps) [self.view addSubview:self.fps];
    [self.view setNeedsLayout]; [self.view layoutIfNeeded];
    const char *scale_env = getenv("DM_RENDER_SCALE");
    CGFloat target_w = 960.0, target_h = 540.0;
    if (scale_env) {
        if (scale_env[0] == '0' && scale_env[1] && scale_env[2] == '6') {
            target_w = 854.0; target_h = 480.0; // 480p (0.67x)
        } else if (scale_env[0] == '1' && scale_env[1] && scale_env[2] == '5') {
            target_w = 1920.0; target_h = 1080.0; // 1080p (1.5x)
        } else if (scale_env[0] == '1') {
            target_w = 1280.0; target_h = 720.0; // 720p (1.0x)
        }
    }
    g_layer.drawableSize = CGSizeMake(target_w, target_h);
    if (self.view.bounds.size.height > 0) {
        g_layer.contentsScale = target_h / self.view.bounds.size.height;
    }
    [self.view.window makeKeyWindow]; [self.view.window makeKeyAndVisible]; [self becomeFirstResponder]; [self setNeedsUpdateOfScreenEdgesDeferringSystemGestures]; [self setNeedsUpdateOfHomeIndicatorAutoHidden];
    UIApplication.sharedApplication.idleTimerDisabled = YES;
    front_ios_boot();
}
- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    CGRect b = self.view.bounds; if (!self.game) return;
    CGFloat w = b.size.width, h = b.size.height;   // Fit 16:9 into the whole screen
    if (w / h > 16.0 / 9.0) w = h * 16.0 / 9.0; else h = w * 9.0 / 16.0;
    self.game.frame = CGRectMake(floor((b.size.width - w) / 2), floor((b.size.height - h) / 2), w, h);
    if (self.fps) {   // the top row's free stretch: right of DmGamepad.m's L3 key (102 + 17 of its units from the safe edge), level with − / + (22 units down); u is its unit
        CGRect s = UIEdgeInsetsInsetRect(b, self.view.safeAreaInsets); CGFloat u = MIN(b.size.height / 430.0, 1.3);
        self.fps.frame = CGRectMake(floor(CGRectGetMinX(s) + 130 * u), floor(CGRectGetMinY(s) + 22 * u - 11), 64, 22);
    }
}
- (void)viewDidAppear:(BOOL)a {
    [super viewDidAppear:a];
    if (!front_ios_boot_ok() && front_ios_boot_message() && !self.presentedViewController) {   // a slim build whose game file image is missing or another version (main.m)
        UIAlertController *a = [UIAlertController alertControllerWithTitle:@"Game files" message:@(front_ios_boot_message()) preferredStyle:UIAlertControllerStyleAlert];
        [a addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:a animated:YES completion:nil];
    }
    if (self.launched || !front_ios_boot_ok()) return;
    self.launched = YES; g_root = self;
    if (!dm_show_launcher((__bridge void *)self, launcher_done)) [self startGame];   // the settings screen first (Launcher.swift), when the app has one
}
- (BOOL)canBecomeFirstResponder { return YES; }
- (BOOL)prefersHomeIndicatorAutoHidden { return YES; }
- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures { return UIRectEdgeAll; }   // Edge gestures need two swipes, to avoid accidental exits
- (BOOL)prefersStatusBarHidden { return YES; }
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }
@end
UIViewController *front_ios_root(void) { return [DmRootVC new]; }

// Thermal state and screen brightness for the power and present rows every 300 frames (hle_nvn.c; its weak defaults return -1 on the Mac). thermalState: 0 nominal, 1 fair, 2 serious, 3 critical.
// Brightness is read on the main thread at start and on each change; every change of the thermal state and of Low Power Mode (which lowers the CPU clock) is logged with the time since launch
static _Atomic double g_brightness = -1;
int dm_thermal_now(void) { return (int)NSProcessInfo.processInfo.thermalState; }
int dm_low_power_now(void) { return NSProcessInfo.processInfo.lowPowerModeEnabled; }   // the frame step does not probe in it (hle_nvn.c fstep_cpu_slowed)
double dm_brightness_now(void) { return g_brightness; }
static void front_ios_power_watch(void) {
    g_brightness = UIScreen.mainScreen.brightness;
    [NSNotificationCenter.defaultCenter addObserverForName:UIScreenBrightnessDidChangeNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n) { (void)n; g_brightness = UIScreen.mainScreen.brightness; }];
    [NSNotificationCenter.defaultCenter addObserverForName:NSProcessInfoThermalStateDidChangeNotification object:nil queue:nil usingBlock:^(NSNotification *n) {
        (void)n; LOG("front end: thermal state → %d (%.0f s after launch)", dm_thermal_now(), (now_ns() - g_t0_ns) / 1e9); }];
    [NSNotificationCenter.defaultCenter addObserverForName:NSProcessInfoPowerStateDidChangeNotification object:nil queue:nil usingBlock:^(NSNotification *n) {
        (void)n; LOG("front end: Low Power Mode → %s (%.0f s after launch)", dm_low_power_now() ? "on" : "off", (now_ns() - g_t0_ns) / 1e9); }];
    LOG("front end: thermal state %d, brightness %.2f, Low Power Mode %s", dm_thermal_now(), g_brightness, dm_low_power_now() ? "on" : "off");
}

// Frame-rate counter: the frames put on screen in the last second (nvn_mtl.m counts them for NVN and for the Vulkan layer alike; frames the display link merged away are not counted).
// On when the IPA was built with it (the NSP script's SHOW_FPS / --show-fps → DMShowFPS in Info.plist); DM_SHOW_FPS=0 / 1 in Documents/env.txt overrides that without a rebuild. NULL when off
uint64_t mtl_present_count(void);
static UILabel *front_ios_fps_label(void) {
    const char *e = getenv("DM_SHOW_FPS");
    if (!(e ? atoi(e) != 0 : [[NSBundle.mainBundle objectForInfoDictionaryKey:@"DMShowFPS"] boolValue])) return nil;
    UILabel *l = [UILabel new];
    l.font = [UIFont monospacedDigitSystemFontOfSize:13 weight:UIFontWeightSemibold]; l.textColor = UIColor.whiteColor; l.textAlignment = NSTextAlignmentCenter;
    l.backgroundColor = [UIColor colorWithWhite:0 alpha:0.45]; l.layer.cornerRadius = 6; l.layer.masksToBounds = YES; l.userInteractionEnabled = NO;
    l.text = @"-- fps";
    __block uint64_t n0 = mtl_present_count(); __block double t0 = CACurrentMediaTime();
    [NSTimer scheduledTimerWithTimeInterval:1.0 repeats:YES block:^(NSTimer *t) {
        (void)t; uint64_t n = mtl_present_count(); double now = CACurrentMediaTime();
        if (now - t0 < 1.5) l.text = [NSString stringWithFormat:@"%.0f fps", (n - n0) / (now - t0)];   // a longer span is the time in the background: no reading
        n0 = n; t0 = now;
    }];
    LOG("front end: frame-rate counter on");
    return l;
}

// Progress screen of the prepare step (front.h front_progress): a dark view over the game's view and the pad, the title, a bar and a count, centered; UIKit views, so it draws while the game's thread waits
static UIView *g_prog; static UILabel *g_prog_count; static UIProgressView *g_prog_bar; static UILabel *g_prog_title;
void front_progress(const char *title, long done, long total) {
    if (!g_layer) return;
    NSString *tt = title ? @(title) : nil;
    dispatch_async(dispatch_get_main_queue(), ^{
        if (!tt) { [g_prog removeFromSuperview]; g_prog = nil; return; }
        if (!g_prog) {
            UIView *root = g_root.view; if (!root) return;
            g_prog = [[UIView alloc] initWithFrame:root.bounds]; g_prog.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
            g_prog.backgroundColor = [UIColor colorWithWhite:0.06 alpha:0.94];
            UIView *box = [[UIView alloc] initWithFrame:CGRectMake(floor((root.bounds.size.width - 320) / 2), floor((root.bounds.size.height - 96) / 2), 320, 96)];
            box.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin | UIViewAutoresizingFlexibleRightMargin | UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleBottomMargin;
            g_prog_title = [[UILabel alloc] initWithFrame:CGRectMake(0, 4, 320, 30)]; g_prog_title.textAlignment = NSTextAlignmentCenter; g_prog_title.textColor = UIColor.whiteColor;
            g_prog_title.font = [UIFont systemFontOfSize:20 weight:UIFontWeightSemibold];
            g_prog_bar = [[UIProgressView alloc] initWithProgressViewStyle:UIProgressViewStyleDefault]; g_prog_bar.frame = CGRectMake(20, 48, 280, 4);
            g_prog_count = [[UILabel alloc] initWithFrame:CGRectMake(0, 64, 320, 22)]; g_prog_count.textAlignment = NSTextAlignmentCenter;
            g_prog_count.textColor = [UIColor colorWithWhite:0.72 alpha:1]; g_prog_count.font = [UIFont monospacedDigitSystemFontOfSize:13 weight:UIFontWeightRegular];
            [box addSubview:g_prog_title]; [box addSubview:g_prog_bar]; [box addSubview:g_prog_count]; [g_prog addSubview:box];
            [root addSubview:g_prog];
        }
        g_prog_title.text = tt; g_prog_bar.progress = total > 0 ? (float)done / (float)total : 0;
        g_prog_count.text = [NSString stringWithFormat:@"%@ of %@", [NSNumberFormatter localizedStringFromNumber:@(done) numberStyle:NSNumberFormatterDecimalStyle],
                             [NSNumberFormatter localizedStringFromNumber:@(total) numberStyle:NSNumberFormatterDecimalStyle]];
    });
}
void *front_metal_layer(void) { return (__bridge void *)g_layer; }
void front_run(void (*guest)(void)) { guest(); }   // Already on main.m's big-stack thread

// Software keyboard: show a UIAlertController on the main thread, the calling thread waits for the result
int front_text_input(const char *title, const char *sub, const char *guide, const char *initial, int max_chars, char *out, int out_cap) {
    (void)max_chars;
    if (!g_layer) return -1;
    __block int r = 0; __block NSString *text = nil;
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    NSString *t = title && *title ? @(title) : @"", *m = [NSString stringWithFormat:@"%s%s%s", sub ? sub : "", sub && *sub && guide && *guide ? "\n" : "", guide ? guide : ""];
    NSString *init = initial ? @(initial) : @"", *ph = guide ? @(guide) : @"";
    dispatch_async(dispatch_get_main_queue(), ^{
        UIAlertController *ac = [UIAlertController alertControllerWithTitle:t message:m preferredStyle:UIAlertControllerStyleAlert];
        [ac addTextFieldWithConfigurationHandler:^(UITextField *f) { f.text = init; f.placeholder = ph; }];
        [ac addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction *x) { (void)x; r = 1; text = ac.textFields.firstObject.text; dispatch_semaphore_signal(done); }]];
        [ac addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:^(UIAlertAction *x) { (void)x; dispatch_semaphore_signal(done); }]];
        UIViewController *vc = nil;
        for (UIScene *s in UIApplication.sharedApplication.connectedScenes) if ([s isKindOfClass:UIWindowScene.class]) for (UIWindow *w in ((UIWindowScene *)s).windows) if (w.isKeyWindow) vc = w.rootViewController;
        if (!vc) { dispatch_semaphore_signal(done); return; }
        [vc presentViewController:ac animated:YES completion:nil];
    });
    // The guest clock keeps running meanwhile, as on the Switch (hle_swkbd.c): a freeze here as well stopped Octopath Traveler 0's frame loop for as long as the box was up and made its sound stutter
    // (4,977 ms and 2,577 ms frames, 5,181 wakeups a second). The inline keyboard freezes around its own call (hle_swkbd.c)
    dispatch_semaphore_wait(done, DISPATCH_TIME_FOREVER);
    if (!r) return 0;
    snprintf(out, out_cap, "%s", text.UTF8String ? text.UTF8String : "");
    return 1;
}

// Save write failed (most likely the phone's storage is full): show a notice on the main thread without blocking the game. hle_fs.c calls this when a save transaction is refused or a mount has to fall back to read-only;
// the iOS front end used not to implement it, so there was only a log line and the player never learned that progress was not being saved
void front_save_failed(int err) {
    LOG("front end: save data write failed errno=%d, telling the player", err);
    dispatch_async(dispatch_get_main_queue(), ^{
        UIViewController *vc = nil;
        for (UIScene *s in UIApplication.sharedApplication.connectedScenes) if ([s isKindOfClass:UIWindowScene.class]) for (UIWindow *w in ((UIWindowScene *)s).windows) if (w.isKeyWindow) vc = w.rootViewController;
        while (vc.presentedViewController) vc = vc.presentedViewController;
        if (!vc) { LOG("[RED] front end: no window for the save-failure alert errno=%d", err); return; }
        NSString *m = err == ENOSPC ? @"Storage is full, so progress was not saved. Free up space and save again."
                                    : [NSString stringWithFormat:@"Saving failed (errno %d); progress was not saved.", err];
        UIAlertController *a = [UIAlertController alertControllerWithTitle:@"Save failed" message:m preferredStyle:UIAlertControllerStyleAlert];
        [a addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [vc presentViewController:a animated:YES completion:nil];
    });
}

// Audio session: the frames RemoteIO asks for in each callback follow the I/O buffer duration, about 21 ms by default on iOS (1024 frames at 48 kHz). The game keeps only 4 blocks × 5 ms = 20 ms in flight,
// so every callback came up 1.3 ms short and was zero-filled, about 47 gaps per second (crackling; reproducible on the Mac by forcing 1024-frame callbacks: 1999 underruns in 2000 callbacks). Ask for 5 ms and the system picks the nearest it supports;
// the category is Playback, as a game's or media app's: the ring / silent switch does not mute it (the default SoloAmbient follows the switch, which silenced the game whenever the phone was on silent) and it still interrupts other apps' audio.
// Set once at boot and again on return to the foreground (the system may reset it after an interruption)
static int g_session_off;   // the last activation failed (another app or a call still held the session): tried again when the app becomes active
void front_ios_audio_session(void) {
    AVAudioSession *s = AVAudioSession.sharedInstance; NSError *e = nil;
    if (![s setCategory:AVAudioSessionCategoryPlayback error:&e]) LOG("[RED] audio session category could not be set: %s", e.localizedDescription.UTF8String);
    [s setPreferredSampleRate:48000 error:nil];
    if (![s setPreferredIOBufferDuration:0.005 error:&e]) LOG("[RED] audio session I/O buffer duration could not be set: %s", e.localizedDescription.UTF8String);
    g_session_off = ![s setActive:YES error:&e];
    if (g_session_off) LOG("[RED] audio session activation failed: %s", e.localizedDescription.UTF8String);
    LOG("audio session: sample rate %.0f Hz, I/O buffer %.2f ms (asked for 5 ms)", s.sampleRate, s.IOBufferDuration * 1000);
}

// Real audio output is suspended (the silent sink paces the game) while the app is in the background or another audio session has interrupted ours (Siri, an alarm, a call).
// Without the interruption observer the AudioUnits stayed "started" while iOS no longer called them, and a game waiting for its buffers back lost its sound until restart.
// All of this runs on the main queue, like the scene callbacks
static int g_audio_bg, g_audio_intr;
static void front_ios_audio_apply(void) { dm_audio_suspend(g_audio_bg || g_audio_intr); }
static void front_ios_audio_watch(void) {
    NSNotificationCenter *nc = NSNotificationCenter.defaultCenter;
    [nc addObserverForName:AVAudioSessionInterruptionNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n) {
        NSUInteger type = [n.userInfo[AVAudioSessionInterruptionTypeKey] unsignedIntegerValue], reason = [n.userInfo[AVAudioSessionInterruptionReasonKey] unsignedIntegerValue];
        if (type == AVAudioSessionInterruptionTypeBegan) { LOG("audio session: interrupted (reason %lu)", (unsigned long)reason); g_audio_intr = 1; }
        else {
            LOG("audio session: interruption ended"); g_audio_intr = 0;
            if (!g_audio_bg) front_ios_audio_session();
        }
        front_ios_audio_apply();
    }];
    [nc addObserverForName:AVAudioSessionMediaServicesWereResetNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n) {
        (void)n; LOG("audio session: the media services were reset; setting the session and the outputs up again");
        front_ios_audio_session(); dm_audio_reset();
    }];
}

// Scene lifecycle (called by SceneDelegate in main.m): 0 resign active, 1 enter background, 2 return to foreground, 3 become active. On entering background, freeze the guest clock and suspend after in-flight GPU work completes (submitting GPU work in background gets the process killed).
// The screen stays on while the game is active: only touches reset the idle timer, so with a controller (or during a cutscene) the screen dimmed and locked mid-game
void front_ios_focus_event(int ev) {
    if (!g_layer) return;
    switch (ev) {
        case 0: dm_gamepad_reset(); dm_focus_set(2); break;
        case 1: UIApplication.sharedApplication.idleTimerDisabled = NO; dm_focus_set(3); g_audio_bg = 1; front_ios_audio_apply(); guest_clock_freeze_for(1, 1); dm_gfx_suspend(1); break;
        case 2: dm_gfx_suspend(0); guest_clock_freeze_for(1, 0); front_ios_audio_session(); g_audio_bg = 0; front_ios_audio_apply(); dm_focus_set(2); break;
        case 3:   // Becoming active again also ends an interruption whose "ended" never came (not every one sends it), and retries a session that would not activate on the way back
            UIApplication.sharedApplication.idleTimerDisabled = YES;
            if (g_audio_intr) { LOG("audio session: active again with no interruption-ended notice; resuming"); g_audio_intr = 0; g_session_off = 1; }
            if (g_session_off) front_ios_audio_session();
            front_ios_audio_apply(); dm_focus_set(1); break;
    }
}
