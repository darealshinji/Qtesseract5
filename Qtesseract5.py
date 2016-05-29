#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-

"""Script permettant la conversion des fichiers SUB en SRT avec interface graphique pour les textes non traduits automatiquements."""


###############################
### Importation des modules ###
###############################
import sys
from concurrent.futures import ThreadPoolExecutor # Permet de le multi calcul
from shutil import copyfile # Permet de copier le fichier sub dans le dossier temporaire de travail
from pathlib import Path # Nécessaire pour la recherche de fichier
from time import sleep # Necessaire pour mettre en pause la convertion

from PyQt5.QtGui import QIcon, QPixmap, QDesktopServices
from PyQt5.QtWidgets import QApplication, QMessageBox, QDesktopWidget, QInputDialog, QPushButton, QFileDialog, QProgressBar, QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel, QSpacerItem, QSizePolicy, QStatusBar
from PyQt5.QtCore import QProcess, QCoreApplication, Qt, QLocale, QTranslator, QLibraryInfo, QCommandLineOption, QCommandLineParser, QTemporaryDir, QStandardPaths, QCryptographicHash, QDir, QThread, QUrl

import Qtesseract5Ressources_rc # Import des images


#############################################################################
def LittleProcess(Command):
    """Petite fonction reccupérant les retours de process simples."""
    ### Liste qui contiendra les retours
    Reply = []


    ### Création du QProcess avec unification des 2 sorties (normale + erreur)
    process = QProcess()
    process.setProcessChannelMode(1)


    ### Lance et attend la fin de la commande
    process.start(Command)
    process.waitForFinished()


    ### Ajoute les lignes du retour dans la liste
    for line in bytes(process.readAllStandardOutput()).decode('utf-8').splitlines():
        Reply.append(line)


    ### Renvoie le resultat
    return(Reply)



#############################################################################
def TesseractConvert(File):
    """Fonction clée permettant la conversion des images en textes avec Tesseract."""
    ### En cas d'annulation du travail via le soft
    if not GlobalVar["ProgressDialogClose"]:
        return

    ### En cas d'annulation du travail via un fichier exterieur
    elif Path(GlobalVar["FolderTemp"], "Stop").exists():
        GlobalVar["ProgressDialog"].reject()
        GlobalVar["ProgressDialogClose"] = 0
        return


    ### En cas de pause, utilisation d'un fichier pour permettre de mettre en pause depuis l'exterieur
    while Path(GlobalVar["FolderTemp"], "Pause").exists():
        ## Si la fenetre est fermée pendant la pause, on quite
        if not GlobalVar["ProgressDialogClose"] or Path(GlobalVar["FolderTemp"], "Stop").exists():
            return

        ## Sinon on attend la reprise
        else:
            sleep(1)


    ### Création du QProcess avec unification des 2 sorties (normale + erreur)
    process = QProcess()


    ### Reconnaissance de l'image suivante
    process.start('tesseract -l {0} "{1}" "{1}"'.format(GlobalVar["l"], File))
    process.waitForFinished()


    ### Calcul de la progression
    ## Décompte du nombre de fichier traité avec création du pourcentage
    GlobalVar["FilesDone"] += 1

    ## Progression de la fenetre ne necessitant pas de calcul
    if not GlobalVar["g"]:
        GlobalVar["ProgressBar"].setValue(GlobalVar["FilesDone"])

    ## Progression pourcentage
    elif not GlobalVar["p"]:
        GlobalVar["Pourcentage"] = int((GlobalVar["FilesDone"] * 100) / GlobalVar["TotalSubtitles"])

        ## Envoie du pourcentage si different du précédant
        if GlobalVar["OldPourcentage"] != GlobalVar["Pourcentage"]:
            print(str(GlobalVar["Pourcentage"]), file=sys.stdout)

            # Variable anti doublon
            GlobalVar["OldPourcentage"] = GlobalVar["Pourcentage"]


    ### Recherche des fichiers txt
    ImageFile = Path(File)
    TxtFile = Path("{}.txt".format(ImageFile))

    if TxtFile.stat().st_size == 0: # Si le fichier est vide 0ko
        ## Hash le fichier
        FileHash = bytes(QCryptographicHash.hash(ImageFile.open("rb").read(), QCryptographicHash.Md5).toHex()).decode('utf-8')

        ## Si le FileHash existe déjà, c'est une image doublon
        if FileHash in GlobalVar["MD5Dico"].keys():
            # Ajout du fichier a la liste en lien avec le hash si le fichier n'est pas déjà dans la liste
            #if ImageFile not in GlobalVar["MD5Dico"][FileHash]:
            GlobalVar["MD5Dico"][FileHash].append(ImageFile)

        ## Si le FileHash n'existe pas, ajout d'une nouvelle paire FileHash : fichier
        else:
            GlobalVar["MD5Dico"][FileHash] = [ImageFile]


    ## Si c'était le dernier fichier, on cache la fenetre
    if GlobalVar["FilesDone"] == GlobalVar["TotalSubtitles"]:
        GlobalVar["ProgressDialog"].accept()



#############################################################################
def ErrorMessages(Message):
    """Fonction affichant le message d'erreur dans une fenêtre ou en console."""
    if not GlobalVar["g"]:
        QMessageBox.critical(None, QCoreApplication.translate("main", "Error Message"), Message)

    else:
        print(Message, file=sys.stderr)



#############################################################################
def QuitError(Text):
    """Fonction de fermeture du logiciel."""
    ErrorMessages(Text)

    if not GlobalVar["FolderTempWidget"].remove():
        ErrorMessages(QCoreApplication.translate("main", "Error: The temporary folder was not deleted."))

    app.exit(1) # Ferme l'application
    sys.exit(1) # Ferme le code python



#############################################################################
def PauseTaf():
    if Path(GlobalVar["FolderTemp"], "Pause").exists():
        Path(GlobalVar["FolderTemp"], "Pause").unlink()

    else:
        Path(GlobalVar["FolderTemp"], "Pause").touch()



#############################################################################
def IMGViewer(change):
    """Fonction de gestion de conversion manuelle des sous titres."""
    ### Mise à jour des variables
    Var = GlobalVar["RecognizedNumber"] + change
    GlobalVar["RecognizedNumber"] = Var # Mise à jour du numéro à traiter (0 , +1, -1)
    md5Key = list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]] # Récupération d'une clé
    img = GlobalVar["MD5Dico"][md5Key][0] # Sélectionne la 1ere image de la clé
    txt = Path("{}.txt".format(img)) # Adresse du fichier texte


    ### Affichage de l'image
    GlobalVar["ImageViewer"].setPixmap(QPixmap(str(img)))
    GlobalVar["ImageViewer"].setStatusTip(QCoreApplication.translate("main", "File with the hash: {}.").format(md5Key))


    ### Progression du travail
    Pourcentage = int(((GlobalVar["RecognizedNumber"] + 1) * 100) / GlobalVar["RecognizedTotal"])
    GlobalVar["ImageProgress"].setValue(Pourcentage)


    ### Modifications graphiques
    if GlobalVar["RecognizedNumber"] + 1 == GlobalVar["RecognizedTotal"]:
        ## Blocage du bouton suivant
        GlobalVar["ImageNext"].setEnabled(False)
        GlobalVar["ImageFinish"].setFocus(Qt.TabFocusReason)

    else:
        ## Déblocage du bouton suivant
        GlobalVar["ImageNext"].setEnabled(True)
        GlobalVar["ImageNext"].setFocus(Qt.TabFocusReason)

    if GlobalVar["RecognizedNumber"] == 0:
        ## Blocage du bouton précédant
        GlobalVar["ImagePrevious"].setEnabled(False)
        GlobalVar["ImageNext"].setFocus(Qt.TabFocusReason)
    else:
        ## Déblocage du bouton précédant
        GlobalVar["ImagePrevious"].setEnabled(True)
        GlobalVar["ImageNext"].setFocus(Qt.TabFocusReason)


    ### Si le fichier texte n'est plus vide (en cas de retour en arrière)
    if txt.stat().st_size > 0:
        with txt.open("r") as SubFile:
            text = SubFile.read()
            GlobalVar["ImageTranslate"].setPlainText(text)



#############################################################################
def TextUpdate():
    """Fonction d'écriture du texte de la conversion manuelle des sous titres."""
    ### Récupération du texte et de la clé
    SubText, md5Key = GlobalVar["ImageTranslate"].toPlainText(), list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]]


    ### Si le texte n'est pas vide, on met à jour les fichiers txt
    if SubText:
        ## Traite les images ayant le même md5
        for ImgFile in GlobalVar["MD5Dico"][md5Key]:
            with open("{}.txt".format(ImgFile), "w") as SubFile:
                SubFile.write(SubText)

        ## Mise au propre du texte
        GlobalVar["ImageTranslate"].clear()



#############################################################################
if __name__ == '__main__':
    ####################
    ### QApplication ###
    ####################
    app = QApplication(sys.argv)
    app.setApplicationVersion("1.0") # version de l'application
    app.setApplicationName("Qtesseract5") # nom de l'application
    app.setWindowIcon(QIcon.fromTheme("qtesseract5", QIcon(":/img/qtesseract5.png"))) # icone de l'application

    GlobalVar = {} # Dictionnaire contenant toutes les variables


    ###################
    ### Traductions ###
    ###################
    ### Langue du systeme
    Lang = QLocale().name()


    ### Chargement du fichier qm de traduction (anglais utile pour les textes singulier/pluriel)
    appTranslator = QTranslator() # Création d'un QTranslator
    folder = Path(sys.argv[0]).resolve().parent # Dossier des traductions


    ### Pour la trad française
    if "fr" in Lang:
        find = appTranslator.load("Qtesseract5_fr_FR", str(folder))

        ## Si le fichier n'a pas été trouvé, affiche une erreur et utilise la version anglaise
        if not find:
            QMessageBox(3, "Erreur de traduction", "Aucun fichier de traduction <b>française</b> trouvé.<br/>Utilisation de la langue <b>anglaise</b>.", QMessageBox.Close, None, Qt.WindowSystemMenuHint).exec()

        ## Chargement de la traduction
        else:
            app.installTranslator(appTranslator)

        ## Mise à jour du fichier langage de Qt
        translator_qt = QTranslator() # Création d'un QTranslator
        if translator_qt.load("qt_fr_FR", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            app.installTranslator(translator_qt)



    ########################
    ### Parser de config ###
    ########################
    ### Création des options
    qOption = QCommandLineOption(["q", "quiet"], QCoreApplication.translate("main", "Don't reply informations, optionally."), "", "False")
    pOption = QCommandLineOption(["p", "pourcentage"], QCoreApplication.translate("main", "Don't reply progression in no gui mode, optionally."), "", "False")
    gOption = QCommandLineOption(["g", "no-gui"], QCoreApplication.translate("main", "Hide the progress dialog."), "", "False")
    lOption = QCommandLineOption(["l", "language"], QCoreApplication.translate("main", "Language to use for Tesseract ({})."), QCoreApplication.translate("main", "Lang"), "")
    cOption = QCommandLineOption(["c", "cpu"], QCoreApplication.translate("main", "Number of cpu to use, by default is the max."), QCoreApplication.translate("main", "Number"), str(QThread.idealThreadCount()))
    oOption = QCommandLineOption(["o", "open"], QCoreApplication.translate("main", "Automatically open the SRT file created."), "", "False")


    ### Création du parser
    parser = QCommandLineParser()
    parser.setApplicationDescription(QCoreApplication.translate("main", "This software convert a IDX/SUB file in SRT (text) file with Tesseract, subp2pgm and subptools."))
    parser.addHelpOption()
    parser.addVersionOption()
    parser.addOption(gOption)
    parser.addOption(qOption)
    parser.addOption(lOption)
    parser.addOption(cOption)
    parser.addOption(oOption)
    parser.addOption(pOption)
    parser.addPositionalArgument(QCoreApplication.translate("main", "source"), QCoreApplication.translate("main", "Source IDX file to translate."))
    parser.addPositionalArgument(QCoreApplication.translate("main", "destination"), QCoreApplication.translate("main", "Destination SRT file translated."))
    parser.process(app)



    #################
    ### Variables ###
    #################
    ### Mode silence
    GlobalVar["q"] = parser.isSet(qOption)


    ### Mode sans pourcentage
    GlobalVar["p"] = parser.isSet(pOption)


    ### Nombre de cpu à utiliser
    GlobalVar["c"] = int(parser.value(cOption))


    ### Ouverture automatique du fichier srt
    GlobalVar["o"] = parser.isSet(oOption)


    ### Création d'un dossier temporaire
    while True:
        GlobalVar["FolderTempWidget"] = QTemporaryDir()

        if GlobalVar["FolderTempWidget"].isValid():
            GlobalVar["FolderTemp"] = Path(GlobalVar["FolderTempWidget"].path()) # Dossier temporaire

            print("Temporary folder: {}".format(GlobalVar["FolderTemp"]), file=sys.stdout)

            break


    ### Récupération de la liste des langues de Tesseract et ajout des langues de 3 caracteres
    GlobalVar["TesseractLanguages"] = []

    for Lang in LittleProcess('tesseract --list-langs'):
        if len(Lang) == 3:
            GlobalVar["TesseractLanguages"].append(Lang)


    ### Mode gui
    GlobalVar["g"] = parser.isSet(gOption)


    ### Recherche les 3 logiciels necessaires
    for executable in ["tesseract", "subp2pgm", "subptools"]:
        ## Recherche les executables
        if not QStandardPaths.findExecutable(executable) and not QStandardPaths.findExecutable(executable, [str(folder)]):
            QuitError(QCoreApplication.translate("main", "Error: The {} executable isn't founded.").format(executable))

        ## Définit les adresses des executables
        x = QStandardPaths.findExecutable(executable)
        y = QStandardPaths.findExecutable(executable, [str(folder)])

        ## Définit l'adresse du programme
        if x:
            GlobalVar[executable] = x

        elif y:
            GlobalVar[executable] = y


    ### Fichiers d'entrée
    ## Mode graphique si besoin
    if len(parser.positionalArguments()) == 1 :
        # Regarde si l'argument donné est un fichier IDX
        if Path(parser.positionalArguments()[-1]).suffix in ("idx", "IDX"):
            GlobalVar["IDX"] = Path(parser.positionalArguments()[-1])

        # Regarde si l'argument donné est un fichier SUB
        elif Path(parser.positionalArguments()[-1]).suffix in ("sub", "SUB"):
            GlobalVar["IDX"] = Path(parser.positionalArguments()[-1]).with_suffix("idx")

        else:
            ## Fichier IDX d'entrée
            GlobalVar["IDX"] = Path(QFileDialog.getOpenFileName(None, QCoreApplication.translate("main", "Select the IDX file to translate"), QDir.homePath(), "IDX file (*.idx)")[0])

    ## Mode arguments
    elif len(parser.positionalArguments()) == 2:
        GlobalVar["IDX"] = Path(parser.positionalArguments()[-2])

    else:
        GlobalVar["IDX"] = Path(QFileDialog.getOpenFileName(None, QCoreApplication.translate("main", "Select the IDX file to translate"), QDir.homePath(), "IDX file (*.idx)")[0])


    ## Teste du fichier
    if not GlobalVar["IDX"].is_file():
        QuitError(QCoreApplication.translate("main", "Error: The IDX input file doesn't exists.").format(executable))


    ### Fichiers de sortie
    ## Mode graphique si besoin
    if len(parser.positionalArguments()) < 2:
        ## Fichier SRT de sortie
        GlobalVar["SRT"] = Path(QFileDialog.getSaveFileName(None, QCoreApplication.translate("main", "Select the output SRT file translated"), QDir.homePath(), "Text file (*.srt *.txt)")[0])

    ## Mode arguments
    else:
        GlobalVar["SRT"] = Path(parser.positionalArguments()[-1])

    if GlobalVar["SRT"].is_dir():
        QuitError(QCoreApplication.translate("main", "Error: Qtesseract5 need a SRT output file.").format(executable))


    ### Langue à utiliser
    ## Si aucune langue n'est donnée en argument
    if not parser.value(lOption):
        # Proposition d'une langue
        Language = QInputDialog.getItem(None, QCoreApplication.translate("main", "Choose the language to use"), QCoreApplication.translate("main", "Choose what language use for read the images with Tesseract:"), GlobalVar["TesseractLanguages"], 0, False)

        # Utilisation d'une langue ou arret
        if Language[1]:
            GlobalVar["l"] = Language[0]

        else:
            QuitError(QCoreApplication.translate("main", "Error: The work has been canceled."))

    ## Si la langue donnée en argument mais qu'il n'est pas bon
    elif parser.value(lOption) not in GlobalVar["TesseractLanguages"]:
        # Message d'information
        Window = QMessageBox(QMessageBox.Information, QCoreApplication.translate("main", "Tesseract langs error"), QCoreApplication.translate("main", "The subtitle language is not avaible in Tesseract list langs:\n{}").format("\n".join(GlobalVar["TesseractLanguages"])), QMessageBox.Close, None, Qt.WindowSystemMenuHint)
        Button = QPushButton(QIcon.fromTheme("preferences-desktop-locale", QIcon(":/img/preferences-desktop-locale.png")), QCoreApplication.translate("main", "Use another language"), Window)
        Window.addButton(Button, QMessageBox.YesRole) # Ajout du bouton
        Window.setDefaultButton(QMessageBox.Close)
        Window.exec() # Message d'information

        # Arret du travail
        if Window.buttonRole(Window.clickedButton()) != 5:
            QuitError(QCoreApplication.translate("main", "Error: The work has been canceled."))

        # Proposition d'une autre langue
        OtherLanguage = QInputDialog.getItem(None, QCoreApplication.translate("main", "Use another language"), QCoreApplication.translate("main", "Choose what another language use for read the images with Tesseract:"), GlobalVar["TesseractLanguages"], 0, False)

        # Utilisation d'une autre langue ou arret
        if OtherLanguage[1]:
            GlobalVar["l"] = OtherLanguage[0]

        else:
            QuitError(QCoreApplication.translate("main", "Error: The work has been canceled."))


    ## Langue donnée par commande
    else:
        GlobalVar["l"] = parser.value(lOption)


    ### Initialisation de variables
    GlobalVar["SubImgFiles"] = [] # Liste des fichiers sous titres image
    GlobalVar["MD5Dico"] = {}
    GlobalVar["SUB"] = GlobalVar["IDX"].with_suffix(".sub")
    GlobalVar["IDXTemp"] = Path(GlobalVar["FolderTemp"], GlobalVar["IDX"].name)
    GlobalVar["SUBTemp"] = GlobalVar["IDXTemp"].with_suffix(".sub")
    GlobalVar["Generic"] = GlobalVar["IDXTemp"].with_suffix("")
    GlobalVar["TotalSubtitles"] = 0
    GlobalVar["RecognizedNumber"] = 0
    GlobalVar["RecognizedTotal"] = 0
    GlobalVar["FilesDone"] = 0
    GlobalVar["OldPourcentage"] = -1
    GlobalVar["Pourcentage"] = 0

    # Création de la fenetre de progression
    GlobalVar["ProgressDialogClose"] = 1 # type de fermeture 1 pour ok et 0 pour echec
    GlobalVar["ProgressDialog"] = QDialog(None)
    GlobalVar["ProgressDialog"].setFixedSize(450, 125)
    GlobalVar["ProgressDialog"].setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
    GlobalVar["ProgressBar"] = QProgressBar(None)
    GlobalVar["ProgressBar"].setTextVisible(False)
    GlobalVar["ProgressBar"].setMinimum(0)

    Label = QLabel(QCoreApplication.translate("main", "Convertion of the images by Tesseract in progress..."), GlobalVar["ProgressDialog"])
    Label.setAlignment(Qt.AlignCenter)
    Label.setWordWrap(True)

    Image = QLabel(GlobalVar["ProgressDialog"])
    Image.setPixmap(QIcon.fromTheme("qtesseract5", QIcon(":/img/qtesseract5.png")).pixmap(96, 96))
    Image.setMinimumHeight(96)
    Image.setMinimumWidth(96)

    StopButton = QPushButton(QIcon.fromTheme("process-stop", QIcon(":/img/process-stop.png")), QCoreApplication.translate("main", "Stop work"), None)
    StopButton.clicked.connect(lambda: GlobalVar["ProgressDialog"].reject())

    PauseButton = QPushButton(QIcon.fromTheme("media-playback-pause", QIcon(":/img/media-playback-pause.png")), QCoreApplication.translate("main", "Pause"), None)
    PauseButton.setDefault(True)
    PauseButton.clicked.connect(PauseTaf)

    Spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

    HLayout = QHBoxLayout(None)
    HLayout.addWidget(StopButton)
    HLayout.addItem(Spacer)
    HLayout.addWidget(PauseButton)

    VLayout = QVBoxLayout(None)
    VLayout.addWidget(Label)
    VLayout.addWidget(GlobalVar["ProgressBar"])
    VLayout.addLayout(HLayout)

    Caca = QHBoxLayout(None)
    Caca.addWidget(Image)
    Caca.addLayout(VLayout)

    GlobalVar["ProgressDialog"].setLayout(Caca)


    ##################################
    ### Traitement des sous titres ###
    ##################################
    ### Lit le fichier idx original ligne par ligne et renvoie le tout (ligne + la ligne modifiée) dans un nouveau fichier, permet une meilleur détéction des textes
    with GlobalVar["IDX"].open("r") as fichier_idx:
        with GlobalVar["IDXTemp"].open("w") as new_fichier_idx:
            for ligne in fichier_idx:
                if "custom colors:" in ligne:
                    new_fichier_idx.write("custom colors: ON, tridx: 0000, colors: 000008, 300030, FFFFFF, 9332c8")

                else:
                    new_fichier_idx.write(ligne)


    ### Déplacement dans le dossier temporaire
    copyfile(str(GlobalVar["SUB"]), str(GlobalVar["SUBTemp"]))


    ### Création de la liste des images
    GlobalVar["TotalSubtitles"] = int(LittleProcess('"{}" -n "{}"'.format(GlobalVar["subp2pgm"], GlobalVar["Generic"]))[0].split(" ")[0])

    if not GlobalVar["q"] and GlobalVar["g"]:
        print(QCoreApplication.translate("main", "{} files generated.").format(GlobalVar["TotalSubtitles"]), file=sys.stdout)


    ### Indique à la barre de progression de le nombre de fichier pour eviter les calculs
    GlobalVar["ProgressBar"].setMaximum(GlobalVar["TotalSubtitles"])


    ### Création d'une liste des fichiers sous titres
    for ImageFile in ["*.pgm", "*.tif"]:
        GlobalVar["SubImgFiles"].extend(GlobalVar["FolderTemp"].glob(ImageFile))

    GlobalVar["SubImgFiles"].sort()


    ### Boucle qui traite les images une à une tant qu'il y en a
    if GlobalVar["SubImgFiles"]:
        ## Fonction séparant le travail pour chaque core du processeur, véritable gain de temps
        with ThreadPoolExecutor(max_workers=GlobalVar["c"]) as executor:
            for ImageFile in GlobalVar["SubImgFiles"]:
                executor.submit(TesseractConvert, ImageFile)

            # Dans le cas de l'utilisation d'une fenetre de progresion
            if not GlobalVar["g"]:
                GlobalVar["ProgressDialogClose"] = GlobalVar["ProgressDialog"].exec()

        ## Dans le cas de l'utilisation d'une fenetre de progresion qui a été annulée
        if not GlobalVar["q"] and not GlobalVar["ProgressDialogClose"]:
            QuitError(QCoreApplication.translate("main", "Error: The work has been canceled."))


    ### Si le dico contient des fichiers à reconnaître manuellement
    if GlobalVar["MD5Dico"]:
        GlobalVar["RecognizedTotal"] = len(GlobalVar["MD5Dico"]) # Nombre de soustitres à traiter

        ## Création de la fenetre de reconnaissance manuelle
        GlobalVar["HandConvertDialog"] = QDialog(None)
        GlobalVar["HandConvertDialog"].setMinimumHeight(275)
        GlobalVar["HandConvertDialog"].setMinimumWidth(525)
        GlobalVar["HandConvertDialog"].setWindowFlags(Qt.WindowTitleHint)

        Label = QLabel(QCoreApplication.translate("main", "Tesseract couldn't recognize the subtitle file. It must be done manually."), GlobalVar["HandConvertDialog"])
        Label.setAlignment(Qt.AlignCenter)

        GlobalVar["ImageViewer"] = QLabel(GlobalVar["HandConvertDialog"])
        GlobalVar["ImageViewer"].setMinimumHeight(70)
        GlobalVar["ImageViewer"].setAlignment(Qt.AlignCenter)

        GlobalVar["ImageProgress"] = QProgressBar(GlobalVar["HandConvertDialog"])
        GlobalVar["ImageProgress"].setTextVisible(False)
        GlobalVar["ImageProgress"].setMinimum(1)
        GlobalVar["ImageProgress"].setMaximum(GlobalVar["RecognizedTotal"])

        GlobalVar["ImageTranslate"] = QPlainTextEdit(GlobalVar["HandConvertDialog"])

        GlobalVar["ImagePrevious"] = QPushButton(QIcon.fromTheme("go-previous", QIcon(":/img/go-previous.png")), QCoreApplication.translate("main", "Previous image"), None)
        GlobalVar["ImagePrevious"].clicked.connect(lambda: (TextUpdate(), IMGViewer(-1)))

        GlobalVar["ImageFinish"] = QPushButton(QIcon.fromTheme("dialog-ok", QIcon(":/img/dialog-ok.png")), QCoreApplication.translate("main", "I'm finish"), None)
        GlobalVar["ImageFinish"].clicked.connect(lambda: (TextUpdate(), GlobalVar["HandConvertDialog"].accept()))

        GlobalVar["ImageNext"] = QPushButton(QIcon.fromTheme("go-next", QIcon(":/img/go-next.png")), QCoreApplication.translate("main", "Next image"), None)
        GlobalVar["ImageNext"].clicked.connect(lambda: (TextUpdate(), IMGViewer(1)))

        Spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        HLayout = QHBoxLayout(None)
        HLayout.addWidget(GlobalVar["ImagePrevious"])
        HLayout.addItem(Spacer)
        HLayout.addWidget(GlobalVar["ImageFinish"])
        HLayout.addItem(Spacer)
        HLayout.addWidget(GlobalVar["ImageNext"])

        VLayout = QVBoxLayout(None)
        VLayout.addWidget(Label)
        VLayout.addWidget(GlobalVar["ImageViewer"])
        VLayout.addWidget(GlobalVar["ImageProgress"])
        VLayout.addWidget(GlobalVar["ImageTranslate"])
        VLayout.addLayout(HLayout)

        GlobalVar["HandConvertDialog"].setLayout(VLayout)

        IMGViewer(0)

        GlobalVar["HandConvertDialog"].exec()


    ### Création du fichier srt
    LittleProcess('"{}" -s -w -t srt -i "{}.xml" -o "{}"'.format(GlobalVar["subptools"], GlobalVar["Generic"], GlobalVar["SRT"]))


    ### Teste du fichier et arret du logiciel
    if GlobalVar["SRT"].exists():
        ## Indique que tout est ok
        if not GlobalVar["q"]:
            if not GlobalVar["g"]:
                QMessageBox.information(None, QCoreApplication.translate("main", "Work Finished"), QCoreApplication.translate("main", "The SRT file is created."))

            else:
                print(QCoreApplication.translate("main", "The SRT file is created."), file=sys.stdout)

            # Ouverture automatique du fichier srt créé
            if GlobalVar["o"]:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(GlobalVar["SRT"])))

    else:
        ## Renvoie un erreur de création
        QuitError(QCoreApplication.translate("main", "Error: SRT file isn't created."))


    if not GlobalVar["FolderTempWidget"].remove():
        ErrorMessages(QCoreApplication.translate("main", "Error: The temporary folder was not deleted."))

    sys.exit(0)

