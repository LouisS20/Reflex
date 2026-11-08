# Reflex

Petit logiciel d'automatisation pour Windows, avec une interface soignée :

- **Applications** : quand une appli s'ouvre, une autre se lance (ou des touches sont envoyées), avec délai optionnel et fermeture automatique.
- **Touche Windows** : appui court = un raccourci (par défaut Alt + Espace pour Flow Launcher), appui long = menu Démarrer. Les combinaisons Win + … continuent de marcher.
- **Raccourcis** : clavier, boutons de la souris (molette, boutons 4 et 5), vers un programme ou d'autres touches. Bouton « Enregistrer » pour capturer la combinaison.
- Zone de notification, démarrage avec Windows, journal d'activité.

## Lancer

Python 3.10 ou plus récent :

    pip install -r requirements.txt
    python main.py

## Créer un .exe

Double-clique sur `build.bat`. Le résultat est dans `dist\Reflex.exe`.

## Remarques

- La configuration est dans `%APPDATA%\Reflex\config.json`.
- Pour agir dans les fenêtres lancées en administrateur, Reflex doit aussi tourner en administrateur (bouton dans Réglages).
- Reflex installe des hooks clavier et souris globaux, comme AutoHotkey : un anti-cheat peut le bloquer.
