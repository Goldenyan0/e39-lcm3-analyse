# -*- coding: utf-8 -*-
"""Animations LCM v3.2d (ÉTUDE, rien n'est écrit dans la voiture) (24/11/2026).
v3.2d = v3.2c sans les feux de jour, sans l'arrêt automatique d'A1 à 2 minutes, sans l'arrêt de la phase finale au contact mis,
plus :
- recul : plus d'impulsion du contrôle à froid sur RFS_L / RFS_R (0223 et 0231 = 40, comme KALTUEBERWACHUNG_xx = nicht_aktiv),
  mesure gardée feu allumé (étude : ../desassemblage/ETUDE_recul_scintillement.md) ;
- antibrouillards en feux de virage : clignotant demandé ($88.01 -> NSW_L, $88.04 -> NSW_R, en lecture) et croisement au commodo
  ($86.18), contact mis, hors animation, sans condition de vitesse.
Phase finale d'A2/A3 : les deux angel eyes seuls pendant 40 s (0D3D = 0x28, constante), arrêtée si l'état de verrouillage change ou si A1 se lance.
Base : eeprom_animations_v3.bin (dans la voiture). Longueur 0x01AD (0EEE-0EF2 : bloc 0x13 jamais lu par la ROM, 00 dans la voiture).
Usage : python -I construire_animations_v3_2d.py
"""
import hashlib, os, sys
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from construire_animations_v3 import Asm, ANTI_G, ANTI_D, CLIG_G, CLIG_D, CROI_G, CROI_D, PLEI_G, PLEI_D, ANGE_G, ANGE_D, PERMIS

BASE = os.path.join(ICI, 'eeprom_animations_v3.bin')
SHA_BASE = '72dc912848846cbdc7c1588311186e15d3a6c8acf04a2add31786170ee8af194'
SHA_VERROUILLAGE = '7a110ccc6c9832950de6295a32bc8349236cc732676e78a515143a79935a9ffe'
RAM = 0x0560
NPAS = 11               # 10 feux + 1 pas éteint (A1) ou phase finale (A2/A3)
PAS_TOURS = 18          # tours par pas (environ 100 tours par seconde : 0,18 s)
HOLD_PAS = 231          # 0565 au départ d'A2/A3 : décompté à chaque pas ; 231 - 10 pas = 221, puis 1 pas => phase finale de 222 pas de 0,18 s = 39,96 s (raccompagnement : 40 s)

FIN_A = 0x0D46 + 0x01A8           # 0EEE
FIN_B = 0x0D46 + 0x01AD           # 0EF3 : + 5 octets (0EEE-0EF2)

TABLE = [ANGE_D, ANGE_G, CLIG_D, ANTI_D, CROI_D, PLEI_D, PLEI_G, CROI_G, CLIG_G, ANTI_G]
NOMS = ['Angel D', 'Angel G', 'Clign D', 'Anti D', 'Crois D', 'Plein D', 'Plein G', 'Crois G', 'Clign G', 'Anti G']


def animations(A, hi, lo):
    A.i('ANIM', 0xC6, 0x40); A.i(None, 0xF7, 0x02, 0x23); A.i(None, 0xF7, 0x02, 0x31)  # LDAB #$40 ; STAB $0223 ; STAB $0231 : recul, sans impulsion à froid
    A.i(None, 0xCE, hi, lo)                                                         # LDX #$0560
    # ---------- A1 : appels de phares ----------
    A.i('A1', 0xD6, 0x85); A.i(None, 0xC4, 0x04)                                    # LDAB $85 ; ANDB #$04
    A.i(None, 0xE1, 0x00); A.i(None, 0x27, 0, br='SANSFRONT')                       # CMPB 0,X ; BEQ
    A.i(None, 0xE7, 0x00); A.i(None, 0x27, 0, br='SANSFRONT')                       # STAB 0,X ; BEQ (front descendant)
    A.i(None, 0x6D, 0x03); A.i(None, 0x26, 0, br='ARRET')                           # TST 3,X ; BNE : 1er appel après le lancement = arrêt
    A.i(None, 0x13, 0x87, 0x20, 0, br='SANSFRONT')                                  # BRCLR $87,#$20 : contact coupé, l'appel ne compte pas
    A.i(None, 0x6C, 0x01)                                                           # INC 1,X
    A.i(None, 0x6D, 0x02); A.i(None, 0x26, 0, br='SANSFRONT')                       # TST 2,X ; BNE
    A.i(None, 0x86, 0x03); A.i(None, 0xA7, 0x02)                                    # LDAA #3 ; STAA 2,X
    A.i('SANSFRONT', 0x7D, 0x04, 0x63); A.i(None, 0x26, 0, br='PASSEC')             # TST $0463 ; BNE
    A.i(None, 0x6D, 0x02); A.i(None, 0x27, 0, br='PASSEC')                          # TST 2,X ; BEQ
    A.i(None, 0x6A, 0x02); A.i(None, 0x26, 0, br='PASSEC')                          # DEC 2,X ; BNE
    A.i(None, 0x6F, 0x01)                                                           # CLR 1,X : fenêtre de 3 s écoulée
    A.i('PASSEC', 0xA6, 0x01); A.i(None, 0x81, 0x05); A.i(None, 0x26, 0, br='PASLANCE')
    A.i(None, 0x6F, 0x01); A.i(None, 0x6C, 0x03)                                    # CLR 1,X ; INC 3,X : A1 en cours (plus d'arrêt à 2 min)
    A.i(None, 0x4F); A.i(None, 0x20, 0, br='NHOLD2')                                # CLRA ; BRA : A1, pas de phase finale (0565 = 0)
    A.i('PASLANCE', 0x6D, 0x03); A.i(None, 0x27, 0, br='VERR')
    A.i(None, 0x12, 0x87, 0x20, 0, br='VERR')                                       # contact mis : on continue
    A.i('ARRET', 0x6F, 0x03); A.i(None, 0x6F, 0x06)                                 # CLR 3,X ; CLR 6,X
    A.i('ETEINT', 0x4F); A.i(None, 0x5F); A.i(None, 0xFD, 0x01, 0xC8)              # CLRA ; CLRB ; STD $01C8
    A.i(None, 0xB7, 0x01, 0xCA); A.i(None, 0x39)                                    # STAA $01CA ; RTS
    # ---------- A2/A3 : verrouillage ----------
    A.i('VERR', 0xB6, 0x02, 0x42); A.i(None, 0x84, 0x20); A.i(None, 0x4C)          # LDAA $0242 ; ANDA #$20 ; INCA
    A.i(None, 0xA1, 0x07); A.i(None, 0x27, 0, br='JOUE')                            # CMPA 7,X ; BEQ
    A.i(None, 0xA7, 0x07)                                                           # STAA 7,X
    A.i(None, 0x12, 0x87, 0x20, 0, br='ARRET')                                      # contact mis : pas d'animation, et tout ce qui tourne s'arrête (phase finale, A1)
    A.i('NHOLD', 0x86, HOLD_PAS); A.i('NHOLD2', 0xA7, 0x05)                         # LDAA #231 ; STAA 5,X  (phase finale)
    A.i('DEPART', 0x86, NPAS); A.i(None, 0xA7, 0x06); A.i(None, 0x6F, 0x04)         # LDAA #11 ; STAA 6,X ; CLR 4,X
    # ---------- lecteur commun ----------
    A.i('JOUE', 0xE6, 0x06); A.i(None, 0x27, 0, br='REPOS')                         # LDAB 6,X ; BEQ : rien en cours
    A.i(None, 0xC1, NPAS); A.i(None, 0x22, 0, br='ARRET')                           # CMPB #11 ; BHI (garde-fou)
    A.i(None, 0x6C, 0x04); A.i(None, 0xA6, 0x04)                                    # INC 4,X ; LDAA 4,X
    A.i(None, 0x81, PAS_TOURS); A.i(None, 0x26, 0, br='MONTRE')                     # CMPA #18 ; BNE
    A.i(None, 0x6F, 0x04)                                                           # CLR 4,X
    A.i(None, 0x6D, 0x05); A.i(None, 0x27, 0, br='DECR')                            # TST 5,X ; BEQ : pas (ou plus) de phase finale
    A.i(None, 0x6A, 0x05)                                                           # DEC 5,X
    A.i(None, 0xC1, 0x01); A.i(None, 0x27, 0, br='MONTRE')                          # CMPB #1 ; BEQ : phase finale, on reste
    A.i('DECR', 0x5A); A.i(None, 0xE7, 0x06); A.i(None, 0x26, 0, br='MONTRE')       # DECB ; STAB 6,X ; BNE
    A.i(None, 0x6D, 0x03); A.i(None, 0x27, 0, br='ETEINT')                          # TST 3,X ; BEQ : A2/A3 terminée
    A.i(None, 0xC6, NPAS); A.i(None, 0xE7, 0x06)                                    # LDAB #11 ; STAB 6,X : A1 reboucle
    A.i('MONTRE', 0xC1, 0x01); A.i(None, 0x26, 0, br='NORMAL')                      # CMPB #1 ; BNE
    A.i(None, 0x6D, 0x03); A.i(None, 0x26, 0, br='ETEINT')                          # TST 3,X ; BNE : pause d'A1
    A.i(None, 0xCC, 0x01, 0x20); A.i(None, 0x20, 0, br='ECRIT')                     # LDD #$0120 ; BRA : angel eyes G et D (01C9 = 01, 01CA = 20)
    A.i('NORMAL', 0x6D, 0x03); A.i(None, 0x26, 0, br='AVANT')                       # TST 3,X ; BNE : A1 -> ordre direct
    A.i(None, 0x1E, 0x07, 0x20, 0, br='INDEX')                                      # BRSET 7,X,#$20 : verrouillé -> A3
    A.i('AVANT', 0x50); A.i(None, 0xCB, NPAS + 2)                                   # NEGB ; ADDB #13
    A.i('INDEX', 0x58)                                                              # ASLB
    A.i(None, 0x18, 0xCE, 0, 0, br='ABS16:TABLE-4'); A.i(None, 0x18, 0x3A)          # LDY #TABLE-4 ; ABY
    A.i(None, 0xBD, 0, 0, br='ABS:ETEINT')                                          # JSR ETEINT
    A.i(None, 0x18, 0xEC, 0x00)                                                     # LDD 0,Y
    A.i(None, 0xCE, 0x01, 0x00); A.i(None, 0x3A)                                    # LDX #$0100 ; ABX
    A.i(None, 0xA7, 0x00); A.i(None, 0x39)                                          # STAA 0,X ; RTS
    # ---------- au repos : antibrouillards en feux de virage (B = 0 en arrivant) ----------
    A.i('REPOS', 0x4F)                                                              # CLRA   (A = 01C9, B = 01CA = 0)
    A.i(None, 0x13, 0x87, 0x20, 0, br='SORTIE')                                     # BRCLR $87,#$20 : contact coupé, rien
    A.i(None, 0x13, 0x86, 0x18, 0, br='SORTIE')                                     # BRCLR $86,#$18 : pas de croisement au commodo
    A.i(None, 0xD6, 0x88); A.i(None, 0xC4, 0x05)                                    # LDAB $88 ; ANDB #$05   clignotant : 01 gauche, 04 droite
    A.i(None, 0x17); A.i(None, 0x3D)                                                # TBA ; MUL   B = côté x côté : 01 ou 10
    A.i(None, 0x58); A.i(None, 0x58)                                                # ASLB ; ASLB  04 (NSW_L) ou 40 (NSW_R)
    A.i(None, 0x17); A.i(None, 0x5F)                                                # TBA ; CLRB
    A.i('SORTIE', 0x36); A.i(None, 0xAA, 0x08); A.i(None, 0x32)                     # PSHA ; ORAA 8,X ; PULA
    A.i(None, 0x27, 0, br='FIN')                                                    # BEQ : rien à allumer ni à éteindre
    A.i('ECRIT', 0xB7, 0x01, 0xC9); A.i(None, 0xF7, 0x01, 0xCA)                     # STAA $01C9 ; STAB $01CA
    A.i(None, 0xA7, 0x08)                                                           # STAA 8,X  (dernier état écrit)
    A.i('FIN', 0x39)                                                                # RTS
    A.i('TABLE', *[v for pas in TABLE for v in entree(pas)])


def entree(pas):
    """(01C8, 01C9, 01CA) avec un seul bit -> (masque, octet bas de l'adresse)."""
    nz = [(i, v) for i, v in enumerate(pas) if v]
    assert len(nz) == 1 and bin(nz[0][1]).count('1') == 1, pas
    return (nz[0][1], 0xC8 + nz[0][0])


def construire():
    ee = open(BASE, 'rb').read()
    assert hashlib.sha256(ee).hexdigest() == SHA_BASE, 'base inattendue (SHA-256)'
    rom = bytearray(0x10000); rom[0x0D00:0x1000] = ee
    assert rom[0x0D42:0x0D46] == bytes([0x01, 0xA8, 0x6B, 0xE8]) and rom[0x0D49] == 0x18, 'en-tête inattendu'
    ver = open(os.path.join(ICI, 'eeprom_verrouillage.bin'), 'rb').read()
    assert hashlib.sha256(ver).hexdigest() == SHA_VERROUILLAGE
    assert ee[0x4B:0x68] == ver[0x4B:0x68] and ee[0x68:0xF2] == ver[0xBF:0x149], 'F1 ou F3-F6 différentes'
    assert rom[0x0D3D] == 0x28, 'durée du raccompagnement (0D3D) différente de 40 s'
    assert all(rom[a] == 0 for a in range(FIN_A, FIN_B)), '0EEE-0EF2 pas à 00'
    labs = {}
    A = Asm(0x0DF2)
    animations(A, RAM >> 8, RAM & 0xFF)
    A.poser(labs)
    labs['TABLE-4'] = labs['TABLE'] - 4
    assert A.fin <= FIN_B, 'trop long : fin %04X > %04X (%d octets de trop)' % (A.fin, FIN_B, A.fin - FIN_B)
    new = bytearray(rom)
    for adr, v in A.octets(labs).items(): new[adr] = v
    for adr in range(A.fin, FIN_B): new[adr] = 0x00
    long_ = FIN_B - 0x0D46
    som = sum(new[0x0D46:0x0D46 + long_]) & 0xFFFF
    new[0x0D42:0x0D46] = bytes([long_ >> 8, long_ & 0xFF, som >> 8, som & 0xFF])
    assert new[0x0D00:0x0D42] == rom[0x0D00:0x0D42] and new[0x0D46:0x0DF2] == rom[0x0D46:0x0DF2], 'codage, en-tête, F1 ou F3-F6 modifiés'
    assert new[FIN_B:0x1000] == rom[FIN_B:0x1000], '0EF3 et la suite modifiés'
    return rom, new, labs, dict(fin=A.fin, libre=FIN_B - A.fin, long=long_, som=som)


def ecrire_csv(nom, avant, apres):
    diff = [(a, avant[a], apres[a]) for a in range(0x0D00, 0x1000) if avant[a] != apres[a]]
    with open(os.path.join(ICI, nom), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('adresse;actuel;nouveau\n')
        for a, o, n in diff: f.write('%04X;%02X;%02X\n' % (a, o, n))
    return diff


if __name__ == '__main__':
    rom, new, labs, info = construire()
    sortie = 'eeprom_animations_v3_2d.bin'
    out = os.path.join(ICI, sortie)
    if os.path.exists(out) and open(out, 'rb').read() != bytes(new[0x0D00:0x1000]):
        raise SystemExit("%s existe déjà avec un autre contenu : je ne l'écrase pas" % sortie)
    open(out, 'wb').write(new[0x0D00:0x1000])
    diff = ecrire_csv('eeprom_animations_v3_2d_octets.csv', rom, new)
    print('v3.2d : fin du code %04X, %d octets libres avant 0EF3, somme 0x%04X, %d octets changés depuis la v3 (%04X-%04X), SHA-256 %s'
          % (info['fin'] - 1, info['libre'], info['som'], len(diff), diff[0][0], diff[-1][0], hashlib.sha256(new[0x0D00:0x1000]).hexdigest()))
    print('   ', {k: '%04X' % x for k, x in labs.items()})
