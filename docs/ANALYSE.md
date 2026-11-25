# LCM III : ce que contient le programme

Analyse faite sur une lecture complète du module (ROM 4000-FFFF stable sur deux lectures, EEPROM 0D23-0FFF),
avec `dis_hc11.py`. Légende : **vérifié** = lu dans le code ou les octets ; **déduit** = conclusion logique du code,
pas observée en fonctionnement.

## 1. Carte mémoire

| Zone | Contenu | Statut |
|---|---|---|
| 0000-007F | Registres du 68HC11 (SCI 0070-0077, PPROG 003B, CONFIG 003F) | vérifié |
| 0080-087F | RAM, 2 Ko. Pile initialisée à 087F | vérifié |
| 0D00-0FFF | EEPROM, 768 octets, programmée par PPROG | vérifié |
| 4000-FFFF | Programme, 48 Ko, non réinscriptible dans la voiture | vérifié |

- Processeur de la famille 68HC11 K/P ; la carte correspond au **MC68HC11PH8** (déduit, marquage de la puce non vu).
- Vecteurs : reset 4000, COP 4014, SCI (bus I/K) D3F4, RTI 7C0A.

### Plan de l'EEPROM (routine de codage C26D-C32C)

| Adresse | Contenu |
|---|---|
| 0D00-0D22 | Zone protégée : lecture refusée de 0CE1 à 0D18, écriture refusée jusqu'à 0D22 |
| 0D23-0D41 | Bloc de codage 0 (options principales) |
| 0D42-0ED4 | Blocs 1 à 13 : **correctif logiciel BMW** (options `PROGRAMMPARAMETER_LCM_1` à `_13`) |
| 0ED5-0EF2 | Jamais lu par la ROM : place libre |
| 0EF3-0F72 | Autres blocs de codage (0EF3 contrôlé par XOR) |
| 0F73-0FFF | Mémoire de défauts et compteurs |

## 2. Le crochet de correctif

- En 531F, la ROM appelle `JSR $7F0B` si l'octet de variante en RAM 04CF (0x18) est égal à `0D49`.
- 7F0B revérifie le correctif tous les 101 passages : somme 16 bits des octets à partir de 0D46, sur la longueur
  `0D42-0D43`, comparée à `0D44-0D45`. Si c'est bon, `0462 = 1`, et la ROM fait `JMP $0D4B` à chaque passage.
- La ROM accepte une longueur dont l'octet haut vaut au plus 01 (7F22) : le correctif peut aller jusqu'à 0EF2.
- L'appel a lieu dans la tâche périodique 4AA6, après la lecture des entrées et avant le calcul des sorties (56FF).
  Cadence : environ 100 passages par seconde (déduit d'une mesure du compteur `0463`).

Points importants :
- La somme n'est revérifiée que tous les 101 passages : un correctif à moitié écrit pourrait s'exécuter. Il faut
  couper par `0D49` avant d'écrire.
- Le correctif BMW écrit **PACTL ($26) = 01** à chaque passage ; c'est la seule écriture de ce registre, qui règle
  la cadence de l'interruption temps réel. Couper le correctif n'est donc pas neutre si le module redémarre
  pendant ce temps (déduit) : remettre `0D49` sans attendre.
- Recoder le LCM avec NCS réécrit les blocs 1 à 13 avec le correctif BMW d'origine : c'est un retour arrière.

### Les fonctions du correctif BMW

| # | Rôle | Avec le codage étudié |
|---|---|---|
| F1 | Remise à zéro de demandes d'éclairage selon la position du commodo | à garder |
| F2 | Fonction d'atelier lancée par le testeur pendant un STATUS_VORGEBEN | inutile en conduite |
| F3 | Clignotant avant gradué en remplacement d'un feu de position en panne (ECE) | indispensable |
| F4 | État du contrôle du contacteur de feux stop à l'endormissement du bus | indispensable |
| F5 | Antibrouillards selon le bouton | à garder |
| F6 | PACTL = 01 à chaque passage | indispensable |
| F7 | Relances de la sortie feu de croisement en défaut, seulement si le contrôle à froid des croisements est désactivé | **code mort** avec ce codage : 126 octets récupérables |

## 3. Les entrées et les sorties

Noms vérifiés en exécutant la routine de la ROM (C364-C4D5) sur la table des entrées-sorties du fichier de diagnostic.

- Entrées : `$85.02` pleins phares, `$85.04` appel de phares, `$85.10` bouton antibrouillards ; `$86.01` / `$86.04`
  clignotant gauche / droit au commodo, `$86.18` croisement ; `$87.20` contact (Kl15).
- Sorties forcées par `01C8-01CB` (ajoutées en OU en 5CEE-5D18) :
  - 01C8 : FL_R 02, FL_L 04, BL_L 08, BL_R 10, BLK_RV 20, BLK_LV 80 ;
  - 01C9 : SL_LV 01, SL_RH 02, NSW_L 04, RFS_L 08, AL_L 10, AL_R 20, NSW_R 40, NSL_R 80 ;
  - 01CA : LWR 02, KZL_R 04, SL_LH 08, BL_M 10, SL_RV 20, BLK_LH 80 ;
  - 01CB : BLK_RH 02, NSL_L 04, SL_RHI 08, SL_LHI 10, RFS_R 80.
- Sur une E39 à anneaux, SL_LV et SL_RV sont les angel eyes (vérifié visuellement sur une voiture).
- Verrouillage : le message 7A du module de carrosserie est recopié en `$0242` ; le bit 20 distingue verrouillé
  et déverrouillé (mesuré).
- Clignotants : la demande est dans `$88.01` / `$88.04`, les warnings dans `$88.10` (chemin 4E15-4E87).
- Durée du raccompagnement (« follow me home ») : octet de codage `0D3D`, chargé en 024D (521C) et décompté
  chaque seconde (524E-5258).

## 4. Commandes de diagnostic (table DD5C)

| Cmd | Rôle |
|---|---|
| 06 | Lecture mémoire. Refuse les adresses 0CE1 à 0D18 |
| 07 | Écriture mémoire, 1 octet par requête : RAM et registres sous 0880 (**dangereux**, rien n'est protégé), EEPROM de 0D23 à 0FFF |
| 08 / 09 | Lecture / écriture d'un bloc de codage (l'écriture remet 0462 à 0) |
| 0C | STATUS_VORGEBEN : 12 octets vers 01C4-01CF, sorties ajoutées en OU pendant 1 500 passages |

## 5. Les limites

- Les messages des boutons du volant (adresse 50, vers la radio ou le téléphone) sont jetés dès la réception :
  le filtre D199 ne garde que les destinations 30, BF, D0 et FF. Les lire demanderait un espion de bus
  d'environ 150 à 200 octets : trop gros.
- Place pour du code : 0EC8-0EF2 avec le correctif BMW complet, beaucoup plus en remplaçant F7 (code mort).
- Le chien de garde (COP) est actif : un correctif qui boucle fait redémarrer le module.
