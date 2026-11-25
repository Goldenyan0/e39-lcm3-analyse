# e39-lcm3-analyse

Analyse du **module d'éclairage LCM III** de la BMW E39 (processeur 68HC11, programme en ROM, 768 octets d'EEPROM),
et outils pour écrire et **tester sur PC** un correctif EEPROM avant de le mettre dans la voiture.

Ce dépôt ne contient **aucun logiciel BMW** : ni lecture de la ROM, ni image EEPROM, ni fichier de données BMW.
Les scripts travaillent sur une lecture que vous avez faite vous-même sur votre propre module.

## Cadre du projet

Projet personnel d'**étude et de rétro-ingénierie**, mené dans un cadre précis : comprendre le logiciel d'un calculateur de série, documenter ce qu'il fait et apprendre à vérifier une modification avant de l'écrire.

- Les modifications de logiciel évoquées ici **ne sont pas homologuées**. Elles ne doivent pas être utilisées sur un véhicule circulant sur la voie publique sans nouvelle réception du véhicule (DREAL en France) et déclaration à l'assureur. Renseignez-vous sur la réglementation de votre pays.
- Ce dépôt ne diffuse **aucun fichier BMW** (ni logiciel, ni lecture de calculateur, ni données de codage) et aucune donnée personnelle.
- Aucune garantie : toute utilisation se fait sous votre seule responsabilité.

## Ce qu'on a trouvé

| Question | Réponse | Statut |
|---|---|---|
| Le programme du LCM est-il réinscriptible ? | Non : la ROM (4000-FFFF) n'a aucune routine de programmation. Seule l'EEPROM (0D00-0FFF) s'écrit | vérifié |
| La ROM exécute-t-elle du code en EEPROM ? | Oui : un **crochet de correctif** appelle `0D4B` à chaque passage, si `0D49` vaut la variante attendue (0x18) et si la somme de contrôle de l'en-tête est juste | vérifié |
| Comment couper le correctif sans risque ? | Mettre `0D49` à une autre valeur que 0x18 : il ne s'exécute plus au passage suivant | déduit du code |
| Peut-on allumer des feux depuis le correctif ? | Oui, comme le fait la commande de diagnostic STATUS_VORGEBEN : les octets `01C8-01CB` sont ajoutés **en OU** aux sorties. Ils ne peuvent qu'allumer, jamais éteindre un feu d'origine | vérifié |
| Pourquoi les feux de recul à LED scintillent-ils ? | Le **contrôle à froid des ampoules** envoie une impulsion sur la sortie éteinte. L'option « feux arrière à LED » la coupe sur les quatre feux arrière, mais pas sur le recul | vérifié |
| Peut-on lire les boutons du volant ? | Non sans espionner le bus : le LCM jette leurs messages dès la réception | vérifié |

Le détail, avec les adresses : [docs/ANALYSE.md](docs/ANALYSE.md) et [docs/RECUL_LED.md](docs/RECUL_LED.md).

## Le contenu

- `desassemblage/dis_hc11.py` : désassembleur 68HC11 (familles K/P, préfixes 18/1A/CD) qui suit le flot d'exécution.
- `animation/emu_hc11.py` : émulateur minimal. Il exécute le correctif sur PC et lève une exception sur toute instruction non prévue : rien n'est deviné.
- `animation/construire_animations_v3.py`, `animation/construire_animations_v3_2d.py` : un assembleur maison et le constructeur d'un correctif d'exemple (animations de feux, recul sans scintillement, antibrouillards en feux de virage).
- `animation/tester_animations_v3_2d.py` : 37 contrôles sur l'émulateur, dont des milliers d'états tirés au hasard. Ils vérifient que seuls les bits de sortie permis sont touchés, que rien n'est écrit en EEPROM et que le code ne boucle jamais.
- `animation/eeprom_animations_v3_2d_octets.csv` : les octets du correctif d'exemple (en-tête et code ajouté seulement).
- `docs/routine_animations_desassemblee.txt` : ce code relu par le désassembleur.

Les scripts de construction sont des **exemples de référence** : ils reconstruisent mon correctif à partir de ma
lecture et vérifient son empreinte. Pour un autre module, il faut partir de sa propre lecture et adapter la base.

## Règles de sécurité

1. Lire et sauvegarder toute l'EEPROM avant d'écrire quoi que ce soit.
2. Tester le correctif sur l'émulateur jusqu'à ce que tous les contrôles passent.
3. Couper le correctif (`0D49`) avant d'écrire, écrire le code, puis la longueur et la somme, et remettre `0D49` en dernier.
4. Relire et comparer après l'écriture.
5. Essayer à l'arrêt. En cas de problème : `0D49` ≠ 0x18, ou recodage du LCM avec NCS, qui réécrit le correctif BMW d'origine.

Un correctif fautif tourne dans le module qui gère l'éclairage : il peut couper des feux. Tout ce qui touche aux
feux stop, aux clignotants et aux feux arrière est exclu des exemples. Vérifiez que vos modifications restent
conformes à la réglementation de votre pays.

## Licence

MIT. Aucune garantie : vous modifiez votre propre véhicule à vos risques.
