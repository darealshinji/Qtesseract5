#! /bin/bash


# Fichier servant :
# - Lors de la creation du paquet sources
# - Apres la creation d'un paquet source, les fichiers sont supprimés, il faut donc les recréer

# if [[ ! $(which "pyrcc5") ]]
# then
#     echo "The pyrcc5 program is missing, installing of pyqt5-dev-tools package."
#     sudo apt-get install pyqt5-dev-tools
# fi

chemin="$(cd "$(dirname "$0")";pwd)"
cd "${chemin}"

# Mise à jour des fichiers ts
pylupdate5 ui_Qtesseract5.ui Qtesseract5.py -ts Qtesseract5_fr_FR.ts

# Convertion des fichiers ts en qm
[[ -e "/usr/lib/x86_64-linux-gnu/qt5/bin/lrelease" ]] && /usr/lib/x86_64-linux-gnu/qt5/bin/lrelease *.ts
[[ -e "/usr/lib/i386-linux-gnu/qt5/bin/lrelease" ]] && /usr/lib/i386-linux-gnu/qt5/bin/lrelease *.ts

# Création d'un fichier source python (contient les icones)
pyrcc5 Qtesseract5Ressources.qrc -o Qtesseract5Ressources_rc.py

# Conversion de l'interface graphique en fichier python
pyuic5 ui_Qtesseract5.ui -o ui_Qtesseract5.py

# Creation d'un systeme d'icone de secoure sur le fichier python ci-dessus
sed -i '/icon = QtGui.QIcon.fromTheme/ s@\([^"]*\)"\([^"]*\)")@\1"\2", QtGui.QIcon(":/img/\2.png"))@g' ui_Qtesseract5.py