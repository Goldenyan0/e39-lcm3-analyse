# -*- coding: utf-8 -*-
"""Animations LCM v3 (ÉTUDE, rien n'est écrit dans la voiture) (23/11/2026).

- A1 (contact mis, 5 appels de phares en moins de 3 s) : chenillard en boucle, un seul feu à la fois, pas de 0,32 s :
  Anti G, Clign G, Crois G, Plein G, Angel G, Angel D, Plein D, Crois D, Clign D, Anti D, puis on recommence.
  Arrêt au premier des trois : 1er appel de phares après le lancement, 2 minutes, contact coupé. Aucune condition de vitesse.
- A2 (déverrouillage) : 15 pas (4,8 s) = table lue de la fin vers le début.
- A3 (verrouillage) : A2 à l'envers = table lue du début vers la fin.
- Déclencheur A2/A3 : changement du bit 20 de $0242 par rapport à 0567, contact coupé, à n'importe quel tour
  (plus besoin de la fin d'acquittement $99). 0567 est mis à jour aussi contact mis.

Une seule table de 15 pas sert aux trois animations :
  pas 0-4  : les deux côtés ensemble, Angel, Plein, Crois, Clign, Anti ;
  pas 5-14 : un feu à la fois, Anti G ... Angel G, Angel D ... Anti D.
A1 lit les pas 5 à 14 en boucle. A3 lit 0 -> 14. A2 lit 14 -> 0.

Disposition : F1 (0D4B) se termine maintenant directement sur F3 ; F3, F4, F5, F6 recopiées telles quelles depuis
l'EEPROM actuelle ; les animations suivent F6 ; longueur du correctif inchangée (0x01A8, donc jusqu'à 0EED).
Base : l'EEPROM actuelle de la voiture (eeprom_verrouillage.bin, écrite le 21/11 à 19:56-19:57).
Usage : python -I construire_animations_v3.py
"""
import hashlib, os
ICI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ICI, 'eeprom_verrouillage.bin')
SHA_BASE = '7a110ccc6c9832950de6295a32bc8349236cc732676e78a515143a79935a9ffe'
SORTIE = 'eeprom_animations_v3.bin'
CSV = 'eeprom_animations_v3_octets.csv'

# RAM (0560-0567, déjà utilisée par les animations actuelles ; 0565 n'est plus utilisée)
#  0 : appel de phares précédent ($85 & 04)     1 : nombre d'appels      2 : fenêtre de 3 s
#  3 : A1 en cours, secondes restantes          4 : compteur de tours (pas de 32 tours = 0,32 s)
#  6 : pas restants (0 = arrêt ; A1 10..1 ; A2/A3 15..1)    7 : dernier état de verrouillage vu (01 ou 21 ; 00 inconnu)
RAM = 0x0560
A1_DUREE = 120          # secondes (tic 0463 = 0 environ toutes les 1,01 s)
A1_PAS, A23_PAS = 10, 15

# Bits des sorties (RAPPORT.md, « Noms des bits ») : (01C8, 01C9, 01CA)
ANTI_G, ANTI_D = (0x00, 0x04, 0x00), (0x00, 0x40, 0x00)      # NSW_L 01C9.04, NSW_R 01C9.40
CLIG_G, CLIG_D = (0x80, 0x00, 0x00), (0x20, 0x00, 0x00)      # BLK_LV 01C8.80, BLK_RV 01C8.20
CROI_G, CROI_D = (0x00, 0x10, 0x00), (0x00, 0x20, 0x00)      # AL_L 01C9.10, AL_R 01C9.20
PLEI_G, PLEI_D = (0x04, 0x00, 0x00), (0x02, 0x00, 0x00)      # FL_L 01C8.04, FL_R 01C8.02
ANGE_G, ANGE_D = (0x00, 0x01, 0x00), (0x00, 0x00, 0x20)      # SL_LV 01C9.01, SL_RV 01CA.20
def deux(a, b): return tuple(x | y for x, y in zip(a, b))
TABLE = [deux(ANGE_G, ANGE_D), deux(PLEI_G, PLEI_D), deux(CROI_G, CROI_D), deux(CLIG_G, CLIG_D), deux(ANTI_G, ANTI_D),
         ANTI_G, CLIG_G, CROI_G, PLEI_G, ANGE_G, ANGE_D, PLEI_D, CROI_D, CLIG_D, ANTI_D]
NOMS = ['Angel G+D', 'Plein G+D', 'Crois G+D', 'Clign G+D', 'Anti G+D',
        'Anti G', 'Clign G', 'Crois G', 'Plein G', 'Angel G', 'Angel D', 'Plein D', 'Crois D', 'Clign D', 'Anti D']
PERMIS = {0x01C8: 0xA6, 0x01C9: 0x75, 0x01CA: 0x20, 0x01CB: 0x00}


class Asm:
    def __init__(self, base): self.base, self.L = base, []
    def i(self, lab, *b, br=None): self.L.append((lab, list(b), br))
    def taille(self): return sum(len(b) for _, b, _ in self.L)
    def poser(self, labs):
        a = self.base
        for lab, b, br in self.L:
            if lab: labs[lab] = a
            a += len(b)
        self.fin = a
    def octets(self, labs):
        out, a = {}, self.base
        for lab, b, br in self.L:
            b = list(b)
            if br and br.startswith('ABS16:'):
                t = labs[br[6:]]; b[2], b[3] = t >> 8, t & 0xFF
            elif br and br.startswith('ABS:'):
                t = labs[br[4:]]; b[1], b[2] = t >> 8, t & 0xFF
            elif br:
                r = labs[br] - (a + len(b)); assert -128 <= r <= 127, (br, r); b[-1] = r & 0xFF
            for k, v in enumerate(b): out[a + k] = v
            a += len(b)
        return out


def construire():
    ee = open(BASE, 'rb').read()
    assert hashlib.sha256(ee).hexdigest() == SHA_BASE, 'base inattendue (SHA-256)'
    rom = bytearray(0x10000); rom[0x0D00:0x1000] = ee
    assert rom[0x0D42:0x0D46] == bytes([0x01, 0xA8, 0x7D, 0x6B]) and rom[0x0D49] == 0x18, 'en-tête inattendu'
    # Fonctions BMW dans l'EEPROM actuelle (relues par le désassembleur, voir routine_verrouillage_desassemblee.txt)
    F1 = bytes(rom[0x0D4B:0x0D68])                    # F1 compactée, 29 octets ; se termine sur F1FIN = 0D68
    F3 = bytes(rom[0x0DBF:0x0DE8]); F4 = bytes(rom[0x0DE8:0x0E04])
    F5 = bytes(rom[0x0E04:0x0E2F]); F6 = bytes(rom[0x0E2F:0x0E49])
    assert rom[0x0D68:0x0D6E] == bytes([0xBD, 0x0D, 0x6D, 0x20, 0x52, 0xCE]), 'fin de F1 inattendue'
    assert F3[:3] == bytes([0xF6, 0x0D, 0x38]) and F4[:3] == bytes([0xF6, 0x0D, 0x26])
    assert F5[:3] == bytes([0xF6, 0x0D, 0x23]) and F6[:2] == bytes([0xC6, 0x01])
    labs = {}
    debut_F3 = 0x0D4B + len(F1)                       # F1 tombe directement sur F3
    # Les sauts de F1 visaient 0D68 (F1FIN). Recalcul des 4 sauts relatifs vers le nouveau F1FIN = début de F3.
    f1 = bytearray(F1)
    for pos, ln in ((0x0D4F, 2), (0x0D58, 4), (0x0D5F, 2), (0x0D61, 4)):
        o = pos - 0x0D4B; off = f1[o + ln - 1]; off = off - 256 if off > 127 else off
        assert pos + ln + off == 0x0D68, ('saut de F1', hex(pos))
        r = debut_F3 - (pos + ln); assert -128 <= r <= 127
        f1[o + ln - 1] = r & 0xFF
    debut_anim = debut_F3 + len(F3) + len(F4) + len(F5) + len(F6)
    hi = RAM >> 8; lo = RAM & 0xFF

    A = Asm(debut_anim)
    # ---------- A1 : appels de phares ----------
    A.i('A1', 0xCE, hi, lo)                                                         # LDX #$0560
    A.i(None, 0xD6, 0x85); A.i(None, 0xC4, 0x04)                                    # LDAB $85 ; ANDB #$04  (S_LH, appel de phares)
    A.i(None, 0xE1, 0x00); A.i(None, 0x27, 0, br='SANSFRONT')                       # CMPB 0,X ; BEQ (pas de changement)
    A.i(None, 0xE7, 0x00); A.i(None, 0x27, 0, br='SANSFRONT')                       # STAB 0,X ; BEQ (front descendant)
    A.i(None, 0x6D, 0x03); A.i(None, 0x26, 0, br='ARRET')                           # TST 3,X ; BNE : A1 en cours -> 1er appel = arrêt
    A.i(None, 0x6C, 0x01)                                                           # INC 1,X   (appel compté)
    A.i(None, 0x6D, 0x02); A.i(None, 0x26, 0, br='SANSFRONT')                       # TST 2,X ; BNE
    A.i(None, 0x86, 0x03); A.i(None, 0xA7, 0x02)                                    # LDAA #3 ; STAA 2,X  (fenêtre de 2 à 3 s)
    A.i('SANSFRONT', 0x7D, 0x04, 0x63); A.i(None, 0x26, 0, br='PASSEC')             # TST $0463 ; BNE  (tic seconde)
    A.i(None, 0x6D, 0x02); A.i(None, 0x27, 0, br='S1')                              # TST 2,X ; BEQ
    A.i(None, 0x6A, 0x02); A.i(None, 0x26, 0, br='S1')                              # DEC 2,X ; BNE
    A.i(None, 0x6F, 0x01)                                                           # CLR 1,X   (fenêtre écoulée)
    A.i('S1', 0x6D, 0x03); A.i(None, 0x27, 0, br='PASSEC')                          # TST 3,X ; BEQ
    A.i(None, 0x6A, 0x03); A.i(None, 0x27, 0, br='ARRET')                           # DEC 3,X ; BEQ  (2 minutes écoulées)
    A.i('PASSEC', 0xA6, 0x01); A.i(None, 0x81, 0x05); A.i(None, 0x26, 0, br='PASLANCE')  # LDAA 1,X ; CMPA #5 ; BNE
    A.i(None, 0x6F, 0x01); A.i(None, 0x6F, 0x02)                                    # CLR 1,X ; CLR 2,X
    A.i(None, 0x86, A1_DUREE); A.i(None, 0xA7, 0x03)                                # LDAA #120 ; STAA 3,X
    A.i(None, 0x86, A1_PAS); A.i(None, 0xA7, 0x06); A.i(None, 0x6F, 0x04)           # LDAA #10 ; STAA 6,X ; CLR 4,X
    A.i('PASLANCE', 0x6D, 0x03); A.i(None, 0x27, 0, br='VERR')                      # TST 3,X ; BEQ
    A.i(None, 0x12, 0x87, 0x20, 0, br='VERR')                                       # BRSET $87,#$20 : contact mis, on continue
    A.i('ARRET', 0x6F, 0x03); A.i(None, 0x6F, 0x06)                                 # CLR 3,X ; CLR 6,X
    A.i(None, 0x20, 0, br='ETEINT')                                                 # BRA ETEINT (tout à 00, RTS)
    # ---------- A2/A3 : verrouillage ----------
    A.i('VERR', 0xB6, 0x02, 0x42); A.i(None, 0x84, 0x20); A.i(None, 0x4C)          # LDAA $0242 ; ANDA #$20 ; INCA -> 01 ou 21
    A.i(None, 0xA1, 0x07); A.i(None, 0x27, 0, br='JOUE')                            # CMPA 7,X ; BEQ (pas de changement)
    A.i(None, 0xA7, 0x07)                                                           # STAA 7,X  (mis à jour, contact mis ou non)
    A.i(None, 0x12, 0x87, 0x20, 0, br='JOUE')                                       # BRSET $87,#$20 : contact mis, pas d'animation
    A.i(None, 0x86, A23_PAS); A.i(None, 0xA7, 0x06); A.i(None, 0x6F, 0x04)          # LDAA #15 ; STAA 6,X ; CLR 4,X
    # ---------- lecteur commun ----------
    A.i('JOUE', 0xE6, 0x06); A.i(None, 0x27, 0, br='FIN')                           # LDAB 6,X ; BEQ  (rien en cours)
    A.i(None, 0xC1, A23_PAS); A.i(None, 0x22, 0, br='ARRET')                        # CMPB #15 ; BHI  (valeur impossible : arrêt, garde-fou)
    A.i(None, 0x6C, 0x04); A.i(None, 0xA6, 0x04); A.i(None, 0x84, 0x1F)             # INC 4,X ; LDAA 4,X ; ANDA #$1F
    A.i(None, 0x26, 0, br='MONTRE')                                                 # BNE  (pas de 32 tours = 0,32 s)
    A.i(None, 0x5A); A.i(None, 0xE7, 0x06); A.i(None, 0x26, 0, br='MONTRE')         # DECB ; STAB 6,X ; BNE
    A.i(None, 0x6D, 0x03); A.i(None, 0x27, 0, br='ETEINT')                          # TST 3,X ; BEQ : A2/A3 terminée
    A.i(None, 0xC6, A1_PAS); A.i(None, 0xE7, 0x06)                                  # LDAB #10 ; STAB 6,X  (A1 : on reboucle)
    A.i('MONTRE', 0x6D, 0x03); A.i(None, 0x26, 0, br='AVANT')                       # TST 3,X ; BNE : A1 -> sens avant
    A.i(None, 0x1E, 0x07, 0x20, 0, br='AVANT')                                      # BRSET 7,X,#$20 : verrouillé -> A3, sens avant
    A.i(None, 0x5A); A.i(None, 0x20, 0, br='INDEX')                                 # DECB ; BRA   A2 : pas = restants - 1 (14 ... 0)
    A.i('AVANT', 0x50); A.i(None, 0xCB, A23_PAS)                                    # NEGB ; ADDB #15   pas = 15 - restants
    A.i('INDEX', 0x86, 0x03); A.i(None, 0x3D)                                       # LDAA #3 ; MUL  (B = 3 x pas)
    A.i(None, 0x18, 0xCE, 0, 0, br='ABS16:TABLE'); A.i(None, 0x18, 0x3A)            # LDY #TABLE ; ABY
    A.i(None, 0x18, 0xA6, 0x00); A.i(None, 0xB7, 0x01, 0xC8)                        # LDAA 0,Y ; STAA $01C8
    A.i(None, 0x18, 0xA6, 0x01); A.i(None, 0xB7, 0x01, 0xC9)                        # LDAA 1,Y ; STAA $01C9
    A.i(None, 0x18, 0xA6, 0x02); A.i(None, 0xB7, 0x01, 0xCA)                        # LDAA 2,Y ; STAA $01CA
    A.i('FIN', 0x39)                                                                # RTS
    A.i('ETEINT', 0x7F, 0x01, 0xC8); A.i(None, 0x7F, 0x01, 0xC9)                    # CLR $01C8 ; CLR $01C9
    A.i(None, 0x7F, 0x01, 0xCA); A.i(None, 0x7F, 0x01, 0xCB)                        # CLR $01CA ; CLR $01CB
    A.i(None, 0x39)                                                                 # RTS
    A.i('TABLE', *[v for pas in TABLE for v in pas])
    A.poser(labs)
    FIN_CORRECTIF = 0x0D46 + 0x01A8                                                 # 0EEE : longueur inchangée
    assert A.fin <= FIN_CORRECTIF, 'trop long : fin %04X > %04X' % (A.fin, FIN_CORRECTIF)

    new = bytearray(rom)
    new[0x0D4B:0x0D4B + len(f1)] = f1
    a = debut_F3
    for f in (F3, F4, F5, F6):
        new[a:a + len(f)] = f; a += len(f)
    assert a == debut_anim
    for adr, v in A.octets(labs).items(): new[adr] = v
    for adr in range(A.fin, FIN_CORRECTIF): new[adr] = 0x00                         # bourrage dans la longueur (jamais exécuté)
    long_ = FIN_CORRECTIF - 0x0D46
    som = sum(new[0x0D46:0x0D46 + long_]) & 0xFFFF
    new[0x0D42:0x0D46] = bytes([long_ >> 8, long_ & 0xFF, som >> 8, som & 0xFF])
    assert long_ == 0x01A8
    assert new[0x0D00:0x0D42] == rom[0x0D00:0x0D42] and new[0x0D46:0x0D4B] == rom[0x0D46:0x0D4B], 'codage ou en-tête modifié'
    assert new[FIN_CORRECTIF:0x1000] == rom[FIN_CORRECTIF:0x1000], '0EEE et la suite modifiés'
    info = dict(debut_F3=debut_F3, debut_anim=debut_anim, fin_code=labs['TABLE'], fin=A.fin,
                libre=FIN_CORRECTIF - A.fin, long=long_, som=som, F=(F1, F3, F4, F5, F6), f1=bytes(f1))
    return rom, new, labs, info


if __name__ == '__main__':
    rom, new, labs, info = construire()
    out = os.path.join(ICI, SORTIE)
    if os.path.exists(out) and open(out, 'rb').read() != bytes(new[0x0D00:0x1000]):
        raise SystemExit('%s existe déjà avec un autre contenu : je ne l\'écrase pas' % SORTIE)
    open(out, 'wb').write(new[0x0D00:0x1000])
    diff = [(a, rom[a], new[a]) for a in range(0x0D00, 0x1000) if rom[a] != new[a]]
    with open(os.path.join(ICI, CSV), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('adresse;actuel;nouveau\n')
        for a, o, n in diff: f.write('%04X;%02X;%02X\n' % (a, o, n))
    print('F1 0D4B-%04X ; F3-F6 %04X-%04X ; animations %04X-%04X ; table %04X-%04X ; %d octets libres avant 0EEE'
          % (info['debut_F3'] - 1, info['debut_F3'], info['debut_anim'] - 1, info['debut_anim'], labs['TABLE'] - 1,
             labs['TABLE'], info['fin'] - 1, info['libre']))
    print('longueur 0x%04X ; somme 0x%04X ; %d octets changés (%04X-%04X) ; SHA-256 %s'
          % (info['long'], info['som'], len(diff), diff[0][0], diff[-1][0], hashlib.sha256(new[0x0D00:0x1000]).hexdigest()))
    print({k: '%04X' % v for k, v in labs.items()})
