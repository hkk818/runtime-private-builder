p = 'dm/tools/sdk_patches.py'
s = open(p, 'r', encoding='utf-8').read()
entry = """  # The Legend of Zelda: Link's Awakening 1.1.0 sdk patch
  "3ae34e689d7a35f13cbf42bfd672af8b": [
    (0x2e7660, "68060039", "7f060039", "disable thread cache"),
    (0x2e7664, "f4000036", "07000014", "skip TLS slot alloc"),
    (0x2e767c, "a0020035", "1f2003d5", "ignore TLS result"),
    (0x2e7784, "68050034", "2b000014", "direct CentralHeap::Alloc"),
    (0x2e788c, "88010034", "0c000014", "direct CentralHeap::Free"),
    (0x2e790c, "48060034", "32000014", "direct CentralHeap::Realloc"),
  ],
"""
idx = s.find('CUTS = {')
assert idx != -1
idx = s.find('\n', idx) + 1
s = s[:idx] + entry + s[idx:]
open(p, 'w', encoding='utf-8').write(s)
print('  [OK] sdk StandardAllocator CentralHeap bypass cuts injected')
