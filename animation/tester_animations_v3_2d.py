# -*- coding: utf-8 -*-
"""Tests sur PC des animations LCM v3.2d (v3.2a + phase finale angel eyes 40 s + recul sans impulsion à froid + antibrouillards en feux de virage).
Aucune écriture vers la voiture. Usage : python -I tester_animations_v3_2d.py
"""
import random, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from emu_hc11 import Emu
import construire_animations_v3_2d as CV

rom, N_, labs, info = CV.construire()
verr = bytearray(0x10000); verr[0x0D00:0x1000] = open(os.path.join(ICI, 'eeprom_verrouillage.bin'), 'rb').read()
ok = True; n_tests = 0
def verdict(nom, cond, detail=''):
    global ok, n_tests
    ok &= bool(cond); n_tests += 1
    print(('OK    ' if cond else 'ÉCHEC ') + nom + (' : ' + detail if detail else ''))

ZERO = (0, 0, 0); ANGES = (0x00, 0x01, 0x20)
T = [tuple(p) for p in CV.TABLE]
def nom(v): return CV.NOMS[T.index(v)] if v in T else ('anges G+D' if v == ANGES else ('éteint' if v == ZERO else '%02X %02X %02X' % v))
A1_ORDRE = CV.NOMS + ['éteint']; A2_ORDRE = CV.NOMS; A3_ORDRE = CV.NOMS[::-1]
PERMIS = {0x01C8: 0xA6, 0x01C9: 0x75, 0x01CA: 0x20, 0x01CB: 0x00}

# ---------- 0) structure ----------
lg = (N_[0x0D42] << 8) | N_[0x0D43]
s = sum(N_[0x0D46:0x0D46 + lg]) & 0xFFFF
verdict('longueur 0x%04X (octet haut <= 01, accepté en 7F22) et somme calculée comme la ROM' % lg, lg == 0x01AD and s == ((N_[0x0D44] << 8) | N_[0x0D45]), '0x%04X' % s)
verdict('codage, F1, F3-F6 et 0EF3-0FFF identiques à la v3 dans la voiture',
        N_[0x0D00:0x0D42] == rom[0x0D00:0x0D42] and N_[0x0D46:0x0DF2] == rom[0x0D46:0x0DF2] and N_[0x0EF3:0x1000] == rom[0x0EF3:0x1000])
verdict('F1 et F3-F6 octet pour octet comme eeprom_verrouillage.bin', N_[0x0D4B:0x0D68] == verr[0x0D4B:0x0D68] and N_[0x0D68:0x0DF2] == verr[0x0DBF:0x0E49])
verdict('durée du raccompagnement codée : 0D3D = 0x28 = 40 s ; phase finale = %d - 10 + 1 = %d pas de 0,18 s' % (CV.HOLD_PAS, CV.HOLD_PAS - 9),
        rom[0x0D3D] == 0x28 and N_[labs['NHOLD'] + 1] == CV.HOLD_PAS)

# ---------- 1) F1-F6 équivalentes ----------
ZONES = list(range(0x0080, 0x0100)) + [0x0189, 0x01BC, 0x0214, 0x015E, 0x0168, 0x01E0, 0x01E5, 0x0540, 0x0463, 0x0242] + list(range(0x01C4, 0x01D0))
COD = [0x0D23, 0x0D26, 0x0D28, 0x0D36, 0x0D38]
rnd = random.Random(2413); diffs = []
for k in range(4000):
    etat = {a: rnd.randrange(256) for a in ZONES}; etat[0x0253] = 0; etat[0x0254] = 0; etat[0x99] = 0
    cod = {a: rnd.randrange(256) for a in COD} if k % 2 else {}
    res = []
    for im in (verr, N_):
        e = Emu(im)
        for a, x in etat.items(): e.m[a] = x
        for a, x in cod.items(): e.m[a] = x
        for a in range(0x0560, 0x0570): e.m[a] = 0
        e.m[0x88] &= 0xFA                                 # pas de clignotant : feux de virage testés à part
        e.m[0x0560] = e.m[0x85] & 0x04; e.m[0x0567] = (e.m[0x0242] & 0x20) + 1
        e.appeler(0x0D4B); res.append(e.m)
    d = [a for a in range(0x0860) if res[0][a] != res[1][a] and not 0x0560 <= a < 0x0570 and a not in (0x0223, 0x0231)]
    if (res[1][0x0223], res[1][0x0231]) != (0x40, 0x40): d.append(0x0223)
    if d: diffs.append((k, ['%04X' % x for x in d[:4]]))
verdict('F1, F3-F6 : même résultat que eeprom_verrouillage.bin (4 000 états, 01C8-01CB compris, $88 sans clignotant) ; 0223 = 0231 = 40 à chaque appel', not diffs, str(diffs[:3]))

# ---------- simulateur ----------
TOUS = set(); MAXPAS = [0]
class Voiture:
    def __init__(self, kl15=True, verr=0x10, moteur=False, etat0=None, crois=False, cligno=0):
        self.e = Emu(N_); m = self.e.m
        m[0x85] = 0x40; m[0x0463] = 50; m[0x0567] = (verr & 0x20) + 1 if etat0 is None else etat0
        self.kl15, self.v242, self.moteur, self.crois, self.cligno = kl15, verr, moteur, crois, cligno
        self.t = 0.0; self.flashs = []; self.tr = []
    def tour(self):
        e = self.e; m = e.m; t = self.t
        m[0x85] = 0x44 if any(a <= t + 1e-9 < a + 0.12 for a in self.flashs) else 0x40
        m[0x87] = 0x32 if self.kl15 else 0x12
        m[0x0242] = self.v242
        m[0x01E7] = 8 if self.moteur and self.kl15 else 0
        m[0x86] = (0x10 if self.crois else 0)
        m[0x88] = self.cligno
        e.ecritures = []
        n0 = [0]; pas0 = e.pas
        def compte(pc): n0[0] += 1; return pas0(pc)
        e.pas = compte; e.appeler(0x0D4B); e.pas = pas0; MAXPAS[0] = max(MAXPAS[0], n0[0])
        for pc, a in e.ecritures:
            if 0x01C8 <= a <= 0x01CB: TOUS.add((a, m[a]))
        m[0x0463] = m[0x0463] - 1 if m[0x0463] else 100
        self.tr.append((round(t, 2), (m[0x01C8], m[0x01C9], m[0x01CA]), m[0x01CB]))
        self.t = round(t + 0.01, 2)
    def jusqua(self, t1):
        while self.t < t1 - 1e-9: self.tour()
    def appels(self, t0, n, ecart=0.3): self.flashs += [round(t0 + ecart * i, 2) for i in range(n)]

def suite(tr, t0=0, t1=1e9):
    out = []
    for t, x, _ in tr:
        if not t0 <= t < t1: continue
        if out and out[-1][0] == x: out[-1][2] = t
        else: out.append([x, t, t])
    return out
def allume(tr, t0=0, t1=1e9): return [x for x in tr if t0 <= x[0] < t1 and (x[1] != ZERO or x[2])]
def anim(v, t0, t1): return [p for p in suite(v.tr, t0, t1) if p[0] != ZERO]

# ---------- 2) A1 ----------
v = Voiture(); v.appels(1.0, 5); v.jusqua(12)
sq = suite(v.tr, 2.2, 12); ordre = [nom(p[0]) for p in sq][:23]
verdict('A1 : Angel D … Anti G, éteint, en boucle', ordre == A1_ORDRE * 2 + [A1_ORDRE[0]], ' > '.join(ordre[:11]))
durees = [round(p[2] - p[1] + 0.01, 2) for p in sq[1:-1]]
verdict('A1 : un seul feu, pas de 0,18 s', all(bin(sum(b << (8 * i) for i, b in enumerate(p[0]))).count('1') <= 1 for p in sq)
        and durees and all(abs(d - 0.18) < 0.011 for d in durees), 'de %.2f à %.2f s' % (min(durees), max(durees)))
v = Voiture(); v.appels(1.0, 5); v.flashs.append(8.0); v.jusqua(10)
verdict('A1 : arrêt au 1er appel de phares, tout à 00', allume(v.tr) and allume(v.tr)[-1][0] < 8.0 and v.tr[-1][1:] == (ZERO, 0))
v = Voiture(); v.appels(1.0, 5); v.jusqua(135)
verdict('A1 : plus d\'arrêt automatique à 2 minutes (encore en cours à 135 s)', allume(v.tr, 134, 135) and v.e.m[0x0563] == 1)
v = Voiture(); v.appels(1.0, 5); v.jusqua(5); v.kl15 = False; v.jusqua(7)
verdict('A1 : arrêt immédiat contact coupé', not allume(v.tr, 5.0))
v = Voiture(kl15=False); v.appels(1.0, 5); v.jusqua(5)
verdict('A1 : 5 appels contact coupé, aucun feu', not allume(v.tr))
v = Voiture(); v.appels(1.0, 4); v.jusqua(5)
verdict('A1 : 4 appels, rien', not allume(v.tr))

# ---------- 3) A2 / A3 avec phase finale ----------
v = Voiture(kl15=False, verr=0x30); v.jusqua(1); v.v242 = 0x10; v.jusqua(46)
sq = anim(v, 0, 46)
verdict('A2 : les 10 pas d\'A1 puis les deux angel eyes seuls', [nom(p[0]) for p in sq] == A2_ORDRE + ['anges G+D'], ' > '.join(nom(p[0]) for p in sq))
h = sq[-1] if sq else None
verdict('A2 : phase finale d\'environ 40 s (222 pas de 0,18 s), puis tout éteint', h and abs(h[2] - h[1] + 0.01 - 39.96) < 0.05 and v.tr[-1][1:] == (ZERO, 0),
        '%.2f s' % (h[2] - h[1] + 0.01) if h else '')
v = Voiture(kl15=False, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(46)
sq = anim(v, 0, 46)
verdict('A3 : A2 à l\'envers puis les deux angel eyes 40 s, puis éteint', [nom(p[0]) for p in sq] == A3_ORDRE + ['anges G+D'] and v.tr[-1][1:] == (ZERO, 0)
        and abs(sq[-1][2] - sq[-1][1] + 0.01 - 39.96) < 0.05)
v = Voiture(kl15=False, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(10); v.kl15 = True; v.jusqua(46)
sq = anim(v, 0, 46)
verdict('phase finale : contact mis ne l\'arrête plus, elle va au bout (40 s) puis tout s\'éteint', sq and nom(sq[-1][0]) == 'anges G+D'
        and abs(sq[-1][2] - sq[-1][1] + 0.01 - 39.96) < 0.05 and v.tr[-1][1:] == (ZERO, 0))
v = Voiture(kl15=False, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(10); v.v242 = 0x10; v.jusqua(13)
sq = anim(v, 10, 13)
verdict('phase finale : déverrouillage -> A2 repart du début', sq and [nom(p[0]) for p in sq][:10] == A2_ORDRE)
v = Voiture(kl15=False, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(8); v.kl15 = True; v.jusqua(9); v.v242 = 0x10; v.jusqua(10)
verdict('phase finale, contact mis, changement de verrouillage : arrêtée, tout à 00 (relecture du 24/11)', not allume(v.tr, 9.02) and v.tr[-1][1:] == (ZERO, 0))
v = Voiture(kl15=True, verr=0x10); v.appels(1.0, 5); v.jusqua(4); v.v242 = 0x30; v.jusqua(5)
verdict('A1 en cours, verrouillage contact mis (verrouillage automatique en roulant) : A1 arrête', not allume(v.tr, 4.02) and v.e.m[0x0563] == 0)
v = Voiture(kl15=True, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(2); v.kl15 = False; v.jusqua(5)
verdict('verrouillage contact mis : rien ensuite', not allume(v.tr))
v = Voiture(kl15=False, verr=0x10, etat0=0x21); v.jusqua(3)
verdict('nuit verrouillée puis déverrouillage sans acquittement : A2', [nom(p[0]) for p in anim(v, 0, 3)][:10] == A2_ORDRE)
v = Voiture(kl15=False, verr=0x10); v.jusqua(1); v.v242 = 0x30; v.jusqua(5); v.kl15 = True; v.appels(5.5, 5); v.jusqua(9)
verdict('A1 lancée pendant la phase finale (contact mis) : la phase s\'arrête, A1 joue sans angel eyes en plus',
        [nom(p[0]) for p in anim(v, 6.75, 9)][:3] == A1_ORDRE[:3] and v.e.m[0x0565] == 0)

# ---------- 4) plus de feux de jour ; feux de virage ; recul ----------
v = Voiture(kl15=True, moteur=True); v.jusqua(2)
verdict('plus de feux de jour : moteur tournant, rien n\'est allumé', not allume(v.tr))
GV, DV = (0, 0x04, 0), (0, 0x40, 0)
v = Voiture(kl15=True, crois=True, cligno=0x01); v.jusqua(1)
verdict('virage : clignotant gauche + croisement -> antibrouillard gauche seul (01C9 = 04)', v.tr[-1][1] == GV and len(suite(v.tr, 0.02, 1)) == 1)
v.cligno = 0x04; v.jusqua(2)
verdict('virage : clignotant droit + croisement -> antibrouillard droit seul (01C9 = 40)', v.tr[-1][1] == DV)
v.cligno = 0; v.jusqua(3)
verdict('virage : fin du clignotant -> éteint', v.tr[-1][1] == ZERO)
v = Voiture(kl15=True, crois=False, cligno=0x01); v.jusqua(1)
verdict('virage : sans croisement au commodo -> rien', not allume(v.tr))
v = Voiture(kl15=False, crois=True, cligno=0x01); v.jusqua(1)
verdict('virage : contact coupé -> rien', not allume(v.tr))
v = Voiture(kl15=True, crois=True, cligno=0x10); v.jusqua(1)
verdict('virage : warnings seuls ($88.10) -> rien', not allume(v.tr))
v = Voiture(kl15=True, crois=True, cligno=0x01); v.jusqua(1); v.kl15 = False; v.jusqua(2)
verdict('virage : contact coupé pendant le virage -> éteint', v.tr[-1][1] == ZERO)
v = Voiture(kl15=True, crois=True, cligno=0x01); v.appels(1.0, 5); v.jusqua(6)
sq = suite(v.tr, 2.25, 6)
verdict('virage + A1 : le chenillard prime (un seul feu à la fois)', [nom(p[0]) for p in sq][:11] == A1_ORDRE)
v = Voiture(kl15=True); v.jusqua(1); v.e.m[0x01C9] = 0x10; v.jusqua(2)
verdict('au repos sans virage : 01C9 n\'est pas réécrit (STATUS_VORGEBEN possible)', v.e.m[0x01C9] == 0x10)
v = Voiture(kl15=True, crois=True, cligno=0x01); v.jusqua(1); v.cligno = 0; v.jusqua(1.5); v.e.m[0x01C9] = 0x10; v.jusqua(2)
verdict('après un virage, une seule écriture de 00 puis plus rien', v.e.m[0x01C9] == 0x10)
v = Voiture(kl15=False); v.jusqua(0.05)
verdict('recul : 0223 = 0231 = 40 à chaque appel, contact mis ou non (impulsion à froid coupée, mesure feu allumé gardée)', v.e.m[0x0223] == 0x40 and v.e.m[0x0231] == 0x40)

# ---------- 5) garde-fous ----------
mauvais = [(a, x) for a, x in TOUS if x & ~PERMIS[a] & 0xFF]
verdict('scénarios : seuls les bits permis (01C8 A6, 01C9 75, 01CA 20), 01CB jamais écrit', not mauvais and not [a for a, x in TOUS if a == 0x01CB], str(mauvais))
rnd = random.Random(96); pb = []
for k in range(2500):
    e = Emu(N_)
    for a in ZONES: e.m[a] = rnd.randrange(256)
    e.m[0x0253] = 0; e.m[0x01E7] = rnd.randrange(256)
    for a in range(0x0560, 0x0570): e.m[a] = rnd.randrange(256)
    for _ in range(40):
        e.ecritures = []; e.appeler(0x0D4B)
        e.m[0x0463] = e.m[0x0463] - 1 if e.m[0x0463] else 100
        for pc, a in e.ecritures:
            if 0x01C8 <= a <= 0x01CB and e.m[a] & ~PERMIS[a] & 0xFF: pb.append((k, '%04X=%02X' % (a, e.m[a])))
            elif 0x0D00 <= a < 0x1000: pb.append((k, 'écriture EEPROM %04X' % a))
            elif labs['ANIM'] <= pc < CV.FIN_B and not (0x0560 <= a <= 0x0568 or 0x01C8 <= a <= 0x01CA or a in (0x0223, 0x0231) or a >= 0x0800):
                pb.append((k, 'écriture %04X depuis %04X' % (a, pc)))
        if e.m[0x0566] > 11: pb.append((k, 'pas restants %d' % e.m[0x0566]))
verdict('RAM 0560-056F au hasard (2 500 x 40 tours) : bits permis, rien en EEPROM, écritures limitées à 0560-0568, 01C8-01CA, 0223, 0231 et la pile', not pb, str(pb[:3]))
verdict('aucune boucle : au plus %d instructions par appel' % MAXPAS[0], MAXPAS[0] < 200)

print('\n%d contrôles. RÉSULTAT : %s' % (n_tests, 'TOUT EST BON' if ok else 'IL Y A DES ÉCHECS'))
sys.exit(0 if ok else 1)
