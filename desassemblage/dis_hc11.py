# -*- coding: utf-8 -*-
"""Désassembleur 68HC11 minimal pour la lecture du LCM III (lecture seule, aucune écriture vers la voiture).

Usage : python -I dis_hc11.py <fichier.bin> <sortie.asm>
Suit le flot d'exécution depuis les vecteurs (FFC0-FFFF) et les points d'entrée trouvés,
puis écrit un listing avec les références croisées.
"""
import sys

# --- Table des opcodes, page 0 -------------------------------------------------
# mode : INH, IM8, IM16, DIR, EXT, IDX, REL, BDIR (BSET/BCLR dir), BIDX, BRDIR (BRSET/BRCLR dir), BRIDX
P0 = {}
def op(c, m, mode):
    P0[c] = (m, mode)

inh = {0x00:'TEST',0x01:'NOP',0x02:'IDIV',0x03:'FDIV',0x04:'LSRD',0x05:'ASLD',0x06:'TAP',0x07:'TPA',
       0x08:'INX',0x09:'DEX',0x0A:'CLV',0x0B:'SEV',0x0C:'CLC',0x0D:'SEC',0x0E:'CLI',0x0F:'SEI',
       0x10:'SBA',0x11:'CBA',0x16:'TAB',0x17:'TBA',0x19:'DAA',0x1B:'ABA',
       0x30:'TSX',0x31:'INS',0x32:'PULA',0x33:'PULB',0x34:'DES',0x35:'TXS',0x36:'PSHA',0x37:'PSHB',
       0x38:'PULX',0x39:'RTS',0x3A:'ABX',0x3B:'RTI',0x3C:'PSHX',0x3D:'MUL',0x3E:'WAI',0x3F:'SWI',
       0x8F:'XGDX',0xCF:'STOP'}
for c, m in inh.items():
    op(c, m, 'INH')
op(0x12, 'BRSET', 'BRDIR'); op(0x13, 'BRCLR', 'BRDIR'); op(0x14, 'BSET', 'BDIR'); op(0x15, 'BCLR', 'BDIR')
op(0x1C, 'BSET', 'BIDX'); op(0x1D, 'BCLR', 'BIDX'); op(0x1E, 'BRSET', 'BRIDX'); op(0x1F, 'BRCLR', 'BRIDX')
for i, m in enumerate(['BRA','BRN','BHI','BLS','BCC','BCS','BNE','BEQ','BVC','BVS','BPL','BMI','BGE','BLT','BGT','BLE']):
    op(0x20 + i, m, 'REL')
op(0x8D, 'BSR', 'REL')
un = {0:'NEG',3:'COM',4:'LSR',6:'ROR',7:'ASR',8:'ASL',9:'ROL',0xA:'DEC',0xC:'INC',0xD:'TST',0xF:'CLR'}
for lo, m in un.items():
    op(0x40 + lo, m + 'A', 'INH'); op(0x50 + lo, m + 'B', 'INH')
    op(0x60 + lo, m, 'IDX'); op(0x70 + lo, m, 'EXT')
op(0x6E, 'JMP', 'IDX'); op(0x7E, 'JMP', 'EXT')
ga = ['SUBA','CMPA','SBCA','SUBD','ANDA','BITA','LDAA','STAA','EORA','ADCA','ORAA','ADDA','CPX','JSR','LDS','STS']
gb = ['SUBB','CMPB','SBCB','ADDD','ANDB','BITB','LDAB','STAB','EORB','ADCB','ORAB','ADDB','LDD','STD','LDX','STX']
for lo in range(16):
    for base, tbl in ((0x80, ga), (0xC0, gb)):
        m = tbl[lo]
        w16 = m in ('SUBD','CPX','LDS','ADDD','LDD','LDX')
        if base + lo not in P0 and m not in ('STAA','STAB','JSR','STS','STD','STX'):
            op(base + lo, m, 'IM16' if w16 else 'IM8')
        op(base + 0x10 + lo, m, 'DIR'); op(base + 0x20 + lo, m, 'IDX'); op(base + 0x30 + lo, m, 'EXT')
op(0x8E, 'LDS', 'IM16')
op(0xCC, 'LDD', 'IM16'); op(0xCE, 'LDX', 'IM16')
# 87, C7, CD, 8D déjà traités ; 87/C7 n'existent pas en immédiat
P0.pop(0x87, None); P0.pop(0xC7, None)
op(0x8D, 'BSR', 'REL')

def xy(m):
    return m.replace('CPX', 'CPY').replace('LDX', 'LDY').replace('STX', 'STY').replace('XGDX', 'XGDY')

P18 = {0x08:('INY','INH'),0x09:('DEY','INH'),0x30:('TSY','INH'),0x35:('TYS','INH'),0x38:('PULY','INH'),
       0x3A:('ABY','INH'),0x3C:('PSHY','INH'),0x8F:('XGDY','INH'),0x8C:('CPY','IM16'),0xCE:('LDY','IM16'),
       0x9C:('CPY','DIR'),0xBC:('CPY','EXT'),0xDE:('LDY','DIR'),0xDF:('STY','DIR'),0xFE:('LDY','EXT'),0xFF:('STY','EXT'),
       0x1C:('BSET','BIDY'),0x1D:('BCLR','BIDY'),0x1E:('BRSET','BRIDY'),0x1F:('BRCLR','BRIDY')}
for c, (m, mode) in P0.items():
    if mode == 'IDX' and c not in (0xA3, 0xAC, 0xAD, 0xEE, 0xEF):
        P18[c] = (m, 'IDY')
P18[0xAD] = ('JSR', 'IDY'); P18[0xAC] = ('CPY', 'IDY'); P18[0xEE] = ('LDY', 'IDY'); P18[0xEF] = ('STY', 'IDY')
P18[0xA3] = None
P18 = {k: v for k, v in P18.items() if v}
P1A = {0x83:('CPD','IM16'),0x93:('CPD','DIR'),0xA3:('CPD','IDX'),0xB3:('CPD','EXT'),
       0xAC:('CPY','IDX'),0xEE:('LDY','IDX'),0xEF:('STY','IDX')}
PCD = {0xA3:('CPD','IDY'),0xAC:('CPX','IDY'),0xEE:('LDX','IDY'),0xEF:('STX','IDY')}

def decode(mem, a):
    """Retourne (longueur, mnémonique, texte opérande, cible_flot, adresse_mémoire, fin_de_flot)."""
    b = mem[a]
    tbl, pre = P0, 0
    if b in (0x18, 0x1A, 0xCD):
        pre = b; tbl = {0x18: P18, 0x1A: P1A, 0xCD: PCD}[b]
        b = mem[a + 1]
    if b not in tbl:
        return None
    m, mode = tbl[b]
    p = a + (2 if pre else 1)
    def u8(i): return mem[p + i]
    def u16(i): return (mem[p + i] << 8) | mem[p + i + 1]
    tgt = ref = None
    if mode == 'INH': n, s = 0, ''
    elif mode == 'IM8': n, s = 1, '#$%02X' % u8(0)
    elif mode == 'IM16': n, s = 2, '#$%04X' % u16(0); ref = u16(0)
    elif mode == 'DIR': n, s = 1, '$%02X' % u8(0); ref = u8(0)
    elif mode == 'EXT': n, s = 2, '$%04X' % u16(0); ref = u16(0)
    elif mode in ('IDX', 'IDY'): n, s = 1, '$%02X,%s' % (u8(0), 'X' if mode == 'IDX' else 'Y')
    elif mode == 'REL':
        n = 1; r = u8(0); r = r - 256 if r > 127 else r; tgt = (p + 1 + r) & 0xFFFF; s = '$%04X' % tgt
    elif mode == 'BDIR': n, s = 2, '$%02X,#$%02X' % (u8(0), u8(1)); ref = u8(0)
    elif mode in ('BIDX', 'BIDY'): n, s = 2, '$%02X,%s,#$%02X' % (u8(0), 'X' if mode == 'BIDX' else 'Y', u8(1))
    elif mode in ('BRDIR', 'BRIDX', 'BRIDY'):
        n = 3; r = u8(2); r = r - 256 if r > 127 else r; tgt = (p + 3 + r) & 0xFFFF
        reg = {'BRDIR': '', 'BRIDX': ',X', 'BRIDY': ',Y'}[mode]
        s = '$%02X%s,#$%02X,$%04X' % (u8(0), reg, u8(1), tgt)
        if mode == 'BRDIR': ref = u8(0)
    length = (p - a) + n
    end = m in ('RTS', 'RTI', 'BRA', 'JMP', 'STOP')
    if m in ('JSR', 'JMP') and mode == 'EXT': tgt = ref
    if m == 'JSR' and mode == 'DIR': tgt = ref
    return length, m, s, tgt, ref, end, mode

EXTRA = [0x7F0B, 0xD463, 0xD4C0, 0xD4EC, 0xD563, 0xD5E1]

def main(src, dst):
    mem = bytearray(open(src, 'rb').read())
    code = {}            # adresse -> decode
    xref = {}            # cible -> liste d'appelants
    entries = []
    for v in range(0xFFC0, 0x10000, 2):
        t = (mem[v] << 8) | mem[v + 1]
        if t >= 0x4000 or 0x0D00 <= t < 0x1000:
            entries.append(t); xref.setdefault(t, []).append('vect %04X' % v)
    # Table des tâches (D775 : pointeur fonction, adresse du drapeau, masque ; 5 octets par entrée)
    t = 0xD775
    while True:
        fn = (mem[t] << 8) | mem[t + 1]
        if fn < 0x4000: break
        entries.append(fn); xref.setdefault(fn, []).append('tache %04X' % t); t += 5
    # Table de sauts 90B0 (8 entrées) et crochet EEPROM 7F0B (appel non résolu statiquement)
    for k in range(8):
        fn = (mem[0x90B0 + 2 * k] << 8) | mem[0x90B1 + 2 * k]
        entries.append(fn); xref.setdefault(fn, []).append('saut 90B0+%d' % k)
    # Table de réception des messages bus (DD5C : commande, source, destination, gestionnaire ; 5 octets)
    t = 0xDD5C
    while True:
        fn = (mem[t + 3] << 8) | mem[t + 4]
        entries.append(fn); xref.setdefault(fn, []).append('msg %02X/%02X>%02X' % (mem[t], mem[t + 1], mem[t + 2]))
        if fn == 0xD196: break
        t += 5
    for extra in EXTRA:
        entries.append(extra); xref.setdefault(extra, []).append('graine')
    seen = set()
    while entries:
        a = entries.pop()
        while a not in seen and a < 0x10000:
            if not (a >= 0x4000 or 0x0D20 <= a < 0x1000):
                break
            d = decode(mem, a)
            if d is None:
                code[a] = ('???', a); break
            seen.add(a); code[a] = d
            ln, m, s, tgt, ref, end, mode = d
            if tgt is not None:
                xref.setdefault(tgt, []).append('%04X %s' % (a, m))
                if tgt not in seen: entries.append(tgt)
            elif ref is not None and m in ('LDX','LDY','LDD','CPX','CPY') and ref >= 0x0D00:
                xref.setdefault(ref, []).append('%04X %s #' % (a, m))
            if end: break
            a += ln
    # Listing
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('; LCM III - désassemblage 68HC11 automatique (flot suivi depuis les vecteurs)\n')
        a = 0x0D00
        ranges = [(0x0D00, 0x1000), (0x4000, 0x10000)]
        for lo, hi in ranges:
            a = lo
            while a < hi:
                if a in code and code[a][0] != '???':
                    ln, m, s, tgt, ref, end, mode = code[a]
                    if a in xref:
                        f.write('\nL%04X:   ; <- %s\n' % (a, ', '.join(xref[a][:12]) + (' ...' if len(xref[a]) > 12 else '')))
                    hx = ' '.join('%02X' % mem[a + i] for i in range(ln))
                    f.write('  %04X  %-14s %-6s %s\n' % (a, hx, m, s))
                    if end: f.write('\n')
                    a += ln
                else:
                    st = a; row = []
                    while a < hi and not (a in code and code[a][0] != '???') and len(row) < 16:
                        row.append(mem[a]); a += 1
                    if a - st == len(row):
                        f.write('  %04X  db %s\n' % (st, ' '.join('%02X' % x for x in row)))
    print('instructions :', len(code), ' cibles :', len(xref))
    return mem, code, xref

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
