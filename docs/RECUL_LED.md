# Feux de recul à LED qui scintillent

## La cause

C'est le **contrôle à froid** des ampoules : le LCM envoie une impulsion très courte sur une sortie éteinte pour
détecter une ampoule grillée. Une ampoule à incandescence ne la montre pas, une LED si.

## Ce que fait la ROM (vérifié)

- Canaux de mesure (table D880) : RFS_L = canal 03, RFS_R = canal 0x11.
- Réglage par canal : table en RAM `0220 + canal`, lue en 5ED6. Bit 80 = impulsion à froid autorisée ;
  bit 40 = mesure quand le feu est allumé.
- Au réveil (4BDD-4C28), tous les canaux reçoivent C0.
- Les options `KALTUEBERWACHUNG_*` mettent certains canaux à 40 : plus d'impulsion, mesure gardée.
- L'option « feux arrière à LED » (routine F200) règle les quatre feux arrière, **pas le recul**.
- `0223` (RFS_L) et `0231` (RFS_R) ne sont jamais réécrits : ils restent à C0. C'est ce manque qui cause le scintillement.
- Impulsions : seulement contact mis, un canal à la fois. Après le réveil, une rafale de quelques secondes,
  puis un flash isolé par feu environ toutes les 32 s (cadence déduite).

## Aucune option de codage ne règle le recul seul

Couper le contrôle à froid de tous les feux est possible par l'octet `0D29`, mais déconseillé.

## Le correctif (8 octets)

```
C6 40       LDAB #$40
F7 02 23    STAB $0223
F7 02 31    STAB $0231
```

Exécuté à chaque passage du correctif EEPROM, il applique au recul le réglage que BMW applique aux autres feux :
plus d'impulsion à froid, mesure gardée quand la marche arrière est engagée. Une ampoule de recul grillée n'est
alors détectée qu'en marche arrière. Ne pas mettre 00 : cela couperait toute surveillance.

Avant d'écrire, lire `0220-023F` contact mis : on attend `0223 = C0` et `0231 = C0`. Après : 40 et 40.

Alternative matérielle : une résistance de charge (« anti-flicker ») sur chaque feu de recul.
