# -*- coding: utf-8 -*-
"""Émulateur 68HC11 minimal, juste ce qu'il faut pour exécuter le correctif EEPROM du LCM III (0D4B-...) sur PC.
Toute instruction non prévue lève une exception : rien n'est deviné.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desassemblage'))
import dis_hc11 as D


class Emu:
    def __init__(self, mem):
        self.m = bytearray(mem)
        self.A = self.B = 0
        self.X = self.Y = 0
        self.SP = 0x087F
        self.N = self.Z = self.V = self.C = 0
        self.ecritures = []          # (pc, adresse)

    # --- mémoire ---
    def rd(self, a): return self.m[a & 0xFFFF]
    def wr(self, a, v, pc):
        self.m[a & 0xFFFF] = v & 0xFF; self.ecritures.append((pc, a & 0xFFFF))
    def rd16(self, a): return (self.rd(a) << 8) | self.rd(a + 1)

    def nz8(self, v): self.N = (v >> 7) & 1; self.Z = int(v & 0xFF == 0)
    def nz16(self, v): self.N = (v >> 15) & 1; self.Z = int(v & 0xFFFF == 0)

    def appeler(self, adr, max_pas=5000):
        """JSR adr depuis une adresse sentinelle ; s'arrête au RTS correspondant."""
        self.SP = 0x087F
        self.m[self.SP] = 0xFF; self.m[self.SP - 1] = 0xFF; self.SP -= 2   # retour vers FFFF
        pc = adr
        for _ in range(max_pas):
            if pc == 0xFFFF:
                return
            pc = self.pas(pc)
        raise RuntimeError('boucle infinie ? pc=%04X' % pc)

    def ea(self, mode, pc, d):
        ln = d[0]
        if mode == 'DIR': return self.rd(pc + ln - 1)
        if mode == 'EXT': return self.rd16(pc + ln - 2)
        if mode == 'IDX': return (self.X + self.rd(pc + ln - 1)) & 0xFFFF
        if mode == 'IDY': return (self.Y + self.rd(pc + ln - 1)) & 0xFFFF
        raise ValueError(mode)

    def pas(self, pc):
        d = D.decode(self.m, pc)
        if d is None:
            raise RuntimeError('opcode inconnu en %04X' % pc)
        ln, mn, s, tgt, ref, end, mode = d
        nxt = (pc + ln) & 0xFFFF
        def opnd8():
            return self.rd(pc + ln - 1) if mode == 'IM8' else self.rd(self.ea(mode, pc, d))
        if mn in ('LDAA', 'LDAB'):
            v = opnd8(); self.nz8(v); self.V = 0
            if mn == 'LDAA': self.A = v
            else: self.B = v
        elif mn in ('STAA', 'STAB'):
            v = self.A if mn == 'STAA' else self.B
            self.wr(self.ea(mode, pc, d), v, pc); self.nz8(v); self.V = 0
        elif mn in ('ANDA', 'ANDB', 'ORAA', 'ORAB', 'EORA', 'EORB'):
            v = opnd8(); r = self.A if mn[-1] == 'A' else self.B
            r = {'AND': r & v, 'ORA': r | v, 'EOR': r ^ v}[mn[:3]]
            self.nz8(r); self.V = 0
            if mn[-1] == 'A': self.A = r
            else: self.B = r
        elif mn in ('CMPA', 'CMPB', 'SUBB', 'SUBA'):
            v = opnd8(); r0 = self.A if mn[-1] == 'A' else self.B
            r = (r0 - v) & 0xFF
            self.C = int(v > r0); self.V = ((r0 ^ v) & (r0 ^ r) & 0x80) >> 7; self.nz8(r)
            if mn.startswith('SUB'):
                if mn[-1] == 'A': self.A = r
                else: self.B = r
        elif mn in ('ADDB', 'ADDA'):
            v = opnd8(); r0 = self.A if mn[-1] == 'A' else self.B; r = r0 + v
            self.C = int(r > 0xFF); r &= 0xFF; self.nz8(r)
            if mn[-1] == 'A': self.A = r
            else: self.B = r
        elif mn in ('CLRA', 'CLRB'):
            if mn == 'CLRA': self.A = 0
            else: self.B = 0
            self.N = 0; self.Z = 1; self.V = 0; self.C = 0
        elif mn in ('TSTA', 'TSTB'):
            self.nz8(self.A if mn == 'TSTA' else self.B); self.V = self.C = 0
        elif mn == 'LSRB':
            self.C = self.B & 1; self.B >>= 1; self.nz8(self.B)
        elif mn in ('CLR', 'TST', 'INC', 'DEC'):
            a = self.ea(mode, pc, d); v = self.rd(a)
            if mn == 'CLR': self.wr(a, 0, pc); self.N = 0; self.Z = 1; self.V = self.C = 0
            elif mn == 'TST': self.nz8(v); self.V = self.C = 0
            elif mn == 'INC': v = (v + 1) & 0xFF; self.wr(a, v, pc); self.nz8(v)
            else: v = (v - 1) & 0xFF; self.wr(a, v, pc); self.nz8(v)
        elif mn in ('BSET', 'BCLR'):
            if mode == 'BDIR': a = self.rd(pc + 1); msk = self.rd(pc + 2)
            elif mode == 'BIDX': a = (self.X + self.rd(pc + 1)) & 0xFFFF; msk = self.rd(pc + 2)
            elif mode == 'BIDY': a = (self.Y + self.rd(pc + 2)) & 0xFFFF; msk = self.rd(pc + 3)
            else: raise ValueError(mode)
            v = self.rd(a); v = (v | msk) if mn == 'BSET' else (v & ~msk & 0xFF)
            self.wr(a, v, pc); self.nz8(v); self.V = 0
        elif mn in ('BRSET', 'BRCLR'):
            if mode == 'BRDIR': a = self.rd(pc + 1); msk = self.rd(pc + 2)
            elif mode == 'BRIDX': a = (self.X + self.rd(pc + 1)) & 0xFFFF; msk = self.rd(pc + 2)
            else: raise ValueError(mode)
            v = self.rd(a)
            ok = (v & msk) == msk if mn == 'BRSET' else (v & msk) == 0
            if ok: nxt = tgt
        elif mn == 'LDX': self.X = self.rd16(pc + 1) if mode == 'IM16' else self.rd16(self.ea(mode, pc, d)); self.nz16(self.X); self.V = 0
        elif mn == 'LDY': self.Y = self.rd16(pc + 2) if mode == 'IM16' else self.rd16(self.ea(mode, pc, d)); self.nz16(self.Y); self.V = 0
        elif mn == 'LDD':
            v = self.rd16(pc + 1) if mode == 'IM16' else self.rd16(self.ea(mode, pc, d))
            self.A, self.B = v >> 8, v & 0xFF; self.nz16(v); self.V = 0
        elif mn == 'XGDX':
            dd = (self.A << 8) | self.B; self.A, self.B = self.X >> 8, self.X & 0xFF; self.X = dd
        elif mn == 'ABY': self.Y = (self.Y + self.B) & 0xFFFF
        elif mn == 'ABX': self.X = (self.X + self.B) & 0xFFFF          # ajouté pour les animations v3.2
        elif mn == 'CBA':                                               # ajouté pour la v3.2b : A - B, drapeaux seulement
            r = (self.A - self.B) & 0xFF
            self.C = int(self.B > self.A); self.V = ((self.A ^ self.B) & (self.A ^ r) & 0x80) >> 7; self.nz8(r)
        elif mn == 'TBA':                                               # ajouté pour la v3.2d
            self.A = self.B; self.nz8(self.A); self.V = 0
        elif mn == 'STD':                                               # ajouté pour la v3.2c
            a = self.ea(mode, pc, d); self.wr(a, self.A, pc); self.wr(a + 1, self.B, pc)
            self.nz16((self.A << 8) | self.B); self.V = 0
        elif mn == 'PSHA':                                              # ajouté pour la v3.2c (ne touche pas aux drapeaux)
            self.m[self.SP] = self.A; self.SP -= 1
        elif mn == 'PULA':                                              # ajouté pour la v3.2c (ne touche pas aux drapeaux)
            self.SP += 1; self.A = self.m[self.SP]
        elif mn in ('BITA', 'BITB'):                                    # ajouté pour la v3.2b : ET sans stocker
            r = (self.A if mn == 'BITA' else self.B) & opnd8(); self.nz8(r); self.V = 0
        elif mn == 'LSRA':                                              # ajouté pour la v3.2b
            self.C = self.A & 1; self.A >>= 1; self.nz8(self.A); self.V = self.C
        elif mn == 'ASLB':                                              # ajouté pour les animations v3.2
            self.C = (self.B >> 7) & 1; self.B = (self.B << 1) & 0xFF; self.nz8(self.B); self.V = self.N ^ self.C
        elif mn in ('BRA', 'BEQ', 'BNE', 'BGE', 'BLT', 'BCC', 'BCS', 'BHI', 'BLS', 'BPL', 'BMI'):
            c = {'BRA': True, 'BEQ': self.Z, 'BNE': not self.Z, 'BGE': not (self.N ^ self.V), 'BLT': self.N ^ self.V,
                 'BCC': not self.C, 'BCS': self.C, 'BHI': not (self.C or self.Z), 'BLS': self.C or self.Z,
                 'BPL': not self.N, 'BMI': self.N}[mn]
            if c: nxt = tgt
        elif mn == 'JSR' and mode == 'EXT':
            r = nxt; self.m[self.SP] = r & 0xFF; self.m[self.SP - 1] = r >> 8; self.SP -= 2; nxt = tgt
        elif mn == 'JMP' and mode == 'EXT':
            nxt = tgt
        elif mn == 'NEGB':
            r = (-self.B) & 0xFF; self.C = int(r != 0); self.V = int(r == 0x80); self.B = r; self.nz8(r)
        elif mn == 'INCA':
            self.A = (self.A + 1) & 0xFF; self.nz8(self.A)
        elif mn == 'DECB':
            self.B = (self.B - 1) & 0xFF; self.nz8(self.B)
        elif mn == 'MUL':                 # D = A x B (non signé), C = bit 7 de B (ajouté pour les animations v3)
            r = self.A * self.B; self.A, self.B = r >> 8, r & 0xFF; self.C = (self.B >> 7) & 1
        elif mn == 'RTS':
            self.SP += 2; nxt = self.rd16(self.SP - 1)
        else:
            raise RuntimeError('instruction non émulée %s en %04X' % (mn, pc))
        return nxt
