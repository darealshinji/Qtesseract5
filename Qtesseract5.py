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

from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QDesktopWidget, QInputDialog, QPushButton, QFileDialog, QProgressDialog
from PyQt5.QtCore import QProcess, QCoreApplication, Qt, QLocale, QTranslator, QLibraryInfo, QCommandLineOption, QCommandLineParser, QTemporaryDir, QStandardPaths, QCryptographicHash, QDir, QThread

from ui_Qtesseract5 import Ui_Qtesseract5 # Utilisé pour la fenêtre principale


##########################
### Fonctions globales ###
##########################
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
    ### En cas d'annulation du travail
    if GlobalVar["ProgressDialog"].wasCanceled():
        return


    ### Création du QProcess avec unification des 2 sorties (normale + erreur)
    process = QProcess()


    ### Reconnaissance de l'image suivante
    process.start('tesseract -l {0} "{1}" "{1}"'.format(GlobalVar["l"], File))
    process.waitForFinished()


    ### Calcul de la progression
    if not GlobalVar["q"]:
        ## Décompte du nombre de fichier traité avec création du pourcentage
        GlobalVar["FilesDone"] += 1
        GlobalVar["Pourcentage"] = int((GlobalVar["FilesDone"] * 100) / GlobalVar["TotalSubtitles"])

        ## Envoie du pourcentage si different du précédant
        if GlobalVar["OldPourcentage"] != GlobalVar["Pourcentage"]:
            # Progression de la fenetre
            if not GlobalVar["g"]:
                GlobalVar["ProgressDialog"].setValue(GlobalVar["Pourcentage"])

            # Progression renvoyé en texte
            else:
                print(str(GlobalVar["Pourcentage"]), file=sys.stdout)

            # Variable anti doublon
            GlobalVar["OldPourcentage"] = GlobalVar["Pourcentage"]


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
class Qtesseract5(QMainWindow):
    """Class permettant la gestion graphique des textes manquants."""
    def __init__(self, parent=None):
        """Fonction d'initialisation appelée au lancement de la classe."""
        ### Commandes à ne pas toucher
        super(Qtesseract5, self).__init__(parent)
        self.ui = Ui_Qtesseract5()
        self.ui.setupUi(self) # Lance la fonction définissant tous les widgets du fichier UI


        ##################
        ### Connexions ###
        ##################
        self.ui.sub_next.clicked.connect(lambda: (self.TextUpdate(), self.IMGViewer(1)))
        self.ui.sub_previous.clicked.connect(lambda: (self.TextUpdate(), self.IMGViewer(-1)))
        self.ui.sub_finish.clicked.connect(lambda: (self.TextUpdate(), self.close()))


        ####################################
        ### Positionnement de la fenetre ###
        ####################################
        size_ecran = QDesktopWidget().screenGeometry() # Taille de l'écran
        self.move((size_ecran.width() - self.geometry().width()) / 2, (size_ecran.height() - self.geometry().height()) / 2)


        ##############################
        ### Lancement des fenetres ###
        ##############################
        ## Appelle de la fonction qui affiche le texte et l'image
        self.IMGViewer(0)




    #========================================================================
    def IMGViewer(self, change):
        """Fonction de gestion de conversion manuelle des sous titres."""
        ### Mise à jour des variables
        Var = GlobalVar["RecognizedNumber"] + change
        GlobalVar["RecognizedNumber"] = Var # Mise à jour du numéro à traiter (0 , +1, -1)
        md5Key = list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]] # Récupération d'une clé
        img = GlobalVar["MD5Dico"][md5Key][0] # Sélectionne la 1ere image de la clé
        txt = Path("{}.txt".format(img)) # Adresse du fichier texte


        ### Affichage de l'image
        self.ui.image_viewer.setPixmap(QPixmap(str(img)))
        self.ui.image_viewer.setStatusTip(QCoreApplication.translate("main", "File with the hash: {}.").format(md5Key))


        ### Progression du travail
        Pourcentage = int(((GlobalVar["RecognizedNumber"] + 1) * 100) / GlobalVar["RecognizedTotal"])
        self.ui.progressBar.setValue(Pourcentage)


        ### Modifications graphiques
        if GlobalVar["RecognizedNumber"] + 1 == GlobalVar["RecognizedTotal"]:
            ## Blocage du bouton suivant
            self.ui.sub_next.setEnabled(False)
            self.ui.sub_finish.setFocus(Qt.TabFocusReason)

        else:
            ## Déblocage du bouton suivant
            self.ui.sub_next.setEnabled(True)
            self.ui.sub_next.setFocus(Qt.TabFocusReason)

        if GlobalVar["RecognizedNumber"] == 0:
            ## Blocage du bouton précédant
            self.ui.sub_previous.setEnabled(False)
            self.ui.sub_next.setFocus(Qt.TabFocusReason)
        else:
            ## Déblocage du bouton précédant
            self.ui.sub_previous.setEnabled(True)
            self.ui.sub_next.setFocus(Qt.TabFocusReason)


        ### Si le fichier texte n'est plus vide (en cas de retour en arrière)
        if txt.stat().st_size > 0:
            with txt.open("r") as SubFile:
                text = SubFile.read()
                self.ui.sub_text.setPlainText(text)


    #========================================================================
    def TextUpdate(self):
        """Fonction d'écriture du texte de la conversion manuelle des sous titres."""
        ### Récupération du texte et de la clé
        SubText, md5Key = self.ui.sub_text.toPlainText(), list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]]


        ### Si le texte n'est pas vide, on met à jour les fichiers txt
        if SubText:
            ## Traite les images ayant le même md5
            for ImgFile in GlobalVar["MD5Dico"][md5Key]:
                with open("{}.txt".format(ImgFile), "w") as SubFile:
                    SubFile.write(SubText)

            ## Mise au propre du texte
            self.ui.sub_text.clear()


#############################################################################
if __name__ == '__main__':
    ####################
    ### QApplication ###
    ####################
    app = QApplication(sys.argv)
    app.setApplicationVersion("1.0") # version de l'application
    app.setApplicationName("Qtesseract5") # nom de l'application
    app.setWindowIcon(QIcon.fromTheme("mkv-extractor-qt5", QIcon(":/img/mkv-extractor-qt5.png"))) # icone de l'application

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
    gOption = QCommandLineOption(["g", "no-gui"], QCoreApplication.translate("main", "Hide the progress dialog."), "", "False")
    lOption = QCommandLineOption(["l", "language"], QCoreApplication.translate("main", "Language to use for Tesseract ({})."), QCoreApplication.translate("main", "Lang"), "")
    cOption = QCommandLineOption(["c", "cpu"], QCoreApplication.translate("main", "Number of cpu to use, by default is the max."), QCoreApplication.translate("main", "Number"), str(QThread.idealThreadCount()))


    ### Création du parser
    parser = QCommandLineParser()
    parser.setApplicationDescription(QCoreApplication.translate("main", "This software convert a IDX/SUB file in SRT (text) file with Tesseract, subp2pgm and subptools."))
    parser.addHelpOption()
    parser.addVersionOption()
    parser.addOption(gOption)
    parser.addOption(qOption)
    parser.addOption(lOption)
    parser.addOption(cOption)
    parser.addPositionalArgument(QCoreApplication.translate("main", "source"), QCoreApplication.translate("main", "Source IDX file to translate."))
    parser.addPositionalArgument(QCoreApplication.translate("main", "destination"), QCoreApplication.translate("main", "Destination SRT file translated."))
    parser.process(app)



    #################
    ### Variables ###
    #################
    ### Mode silence
    GlobalVar["q"] = parser.isSet(qOption)


    ### Nombre de cpu à utiliser
    GlobalVar["c"] = int(parser.value(cOption))


    ### Création d'un dossier temporaire
    while True:
        GlobalVar["FolderTempWidget"] = QTemporaryDir()

        if GlobalVar["FolderTempWidget"].isValid():
            GlobalVar["FolderTemp"] = Path(GlobalVar["FolderTempWidget"].path()) # Dossier temporaire

            if not GlobalVar["q"]:
                print(QCoreApplication.translate("main", "Temporary folder: {}").format(GlobalVar["FolderTemp"]), file=sys.stdout)

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


    ### Fichiers d'entrée et de sortie en mode visuel
    ## Mode graphique si besoin
    if len(parser.positionalArguments()) < 2:
        ## Fichier IDX d'entrée
        GlobalVar["IDX"] = Path(QFileDialog.getOpenFileName(None, QCoreApplication.translate("main", "Select the IDX file to translate"), QDir.homePath(), "IDX file (*.idx)")[0])

        ## Fichier SRT de sortie
        GlobalVar["SRT"] = Path(QFileDialog.getSaveFileName(None, QCoreApplication.translate("main", "Select the output SRT file translated"), QDir.homePath(), "Text file (*.srt *.txt)")[0])

    ## Mode arguments
    else:
        GlobalVar["IDX"] = Path(parser.positionalArguments()[-2])
        GlobalVar["SRT"] = Path(parser.positionalArguments()[-1])


        if not GlobalVar["IDX"].is_file():
            QuitError(QCoreApplication.translate("main", "Error: The IDX input file doesn't exists.").format(executable))

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
    GlobalVar["ProgressDialog"] = QProgressDialog(QCoreApplication.translate("main", "Tesseract progress"), QCoreApplication.translate("main", "Stop work"), 0, 100, None)
    GlobalVar["ProgressDialog"].setWindowModality(Qt.WindowModal)
    GlobalVar["ProgressDialog"].setMinimumHeight(100)
    GlobalVar["ProgressDialog"].setMinimumWidth(300)



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
                GlobalVar["ProgressDialog"].exec()

        # Dans le cas de l'utilisation d'une fenetre de progresion qui a été annulée
        if not GlobalVar["g"]and GlobalVar["ProgressDialog"].wasCanceled():
            QuitError(QCoreApplication.translate("main", "Error: The work has been canceled."))


    ### Recherche des fichiers txt
    for TxtFile in GlobalVar["FolderTemp"].glob("*.txt"):
        if TxtFile.stat().st_size == 0: # Si le fichier est vide 0ko
            ## Récupère le nom du fichier image (enlève l'extension .txt)
            Image = Path(TxtFile.parent, TxtFile.stem)

            ## Hash le fichier
            FileHash = bytes(QCryptographicHash.hash(Image.open("rb").read(), QCryptographicHash.Md5).toHex()).decode('utf-8')

            ## Si le FileHash existe déjà, c'est une image doublon
            if FileHash in GlobalVar["MD5Dico"].keys():
                # Ajout du fichier a la liste en lien avec le hash si le fichier n'est pas déjà dans la liste
                if Image not in GlobalVar["MD5Dico"][FileHash]:
                    GlobalVar["MD5Dico"][FileHash].append(Image)

            ## Si le FileHash n'existe pas, ajout d'une nouvelle paire FileHash : fichier
            else:
                GlobalVar["MD5Dico"][FileHash] = [Image]


    ### Si le dico contient des fichiers à reconnaître manuellement
    if GlobalVar["MD5Dico"]:
        GlobalVar["RecognizedTotal"] = len(GlobalVar["MD5Dico"]) # Nombre de soustitres à traiter

        ## Affichage de la fenetre graphique
        qtesseract5 = Qtesseract5()
        qtesseract5.setAttribute(Qt.WA_DeleteOnClose)
        qtesseract5.show()
        app.exec()


    ### Création du fichier srt
    LittleProcess('"{}" -s -w -t srt -i "{}.xml" -o "{}"'.format(GlobalVar["subptools"], GlobalVar["Generic"], GlobalVar["SRT"]))


    ### Teste du fichier et arret du logiciel
    if GlobalVar["SRT"].exists():
        if not GlobalVar["q"]:
            QMessageBox.information(None, QCoreApplication.translate("main", "Work Finished"), QCoreApplication.translate("main", "The SRT file is created."))

        else:
            print(QCoreApplication.translate("main", "The SRT file is created."), file=sys.stdout)

    else:
        QuitError(QCoreApplication.translate("main", "Error: SRT file isn't created."))


    if not GlobalVar["FolderTempWidget"].remove():
        ErrorMessages(QCoreApplication.translate("main", "Error: The temporary folder was not deleted."))

    sys.exit(0)

