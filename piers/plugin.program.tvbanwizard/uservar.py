#########################################################
import xbmcaddon 
                                      
import os                                             
#########################################################
#########################################################
#         Global Variables - DON'T EDIT!!!              #
#########################################################
ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
PATH = xbmcaddon.Addon().getAddonInfo('path')
ART = os.path.join(PATH, 'resources', 'media')
#########################################################

#########################################################
#        User Edit Variables                            #
#########################################################
ADDONTITLE = '[COLOR azure][B]Tvban[/B][/COLOR] [COLOR tan][B]Wizard[/B][/COLOR]'
BUILDERNAME = 'JoseAndTEB & tvband'
EXCLUDES = [ADDON_ID, 'repository.andtvban']
# Text File with build info in it.
BUILDFILE = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/buildfiles/builds.txt'
# How often you would like it to check for build updates in days
# 0 being every startup of kodi
UPDATECHECK = 0
# Text File with apk info in it.  Leave as 'http://' to ignore
APKFILE = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/buildfiles/apks.txt'
# Text File with Youtube Videos urls.  Leave as 'http://' to ignore
YOUTUBETITLE = '[B][COLOR red]Conciertos[/COLOR] TVBAN [/B]'
YOUTUBEFILE = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/buildfiles/youtube.txt'
# Text File for addon installer.  Leave as 'http://' to ignore
ADDONFILE = 'http://'
# Text File for advanced settings.  Leave as 'http://' to ignore
ADVANCEDFILE = 'https://raw.githubusercontent.com/tvbandroid/tvbandroid.github.io/master/tvband/wizard/json/advanced.json'
#########################################################

#########################################################
#        Theming Menu Items                             #
#########################################################
# If you want to use locally stored icons the place them in the Resources/Art/
# folder of the wizard then use os.path.join(ART, 'imagename.png')
# do not place quotes around os.path.join
# Example:  ICONMAINT     = os.path.join(ART, 'mainticon.png')
#           ICONSETTINGS  = 'https://www.yourhost.com/repo/wizard/settings.png'
# Leave as http:// for default icon
ICONBUILDS = os.path.join(ART, 'builds.png')
ICONMAINT = os.path.join(ART, 'maintenance.png')
ICONSPEED = os.path.join(ART, 'speed.png')
ICONAPK = os.path.join(ART, 'apkinstaller.png')
ICONADDONS = os.path.join(ART, 'addoninstaller.png')
ICONYOUTUBE = os.path.join(ART, 'youtube.png')
ICONSAVE = os.path.join(ART, 'savedata.png')
ICONTRAKT = os.path.join(ART, 'keeptrakt.png')
ICONREAL = os.path.join(ART, 'keepdebrid.png')
ICONLOGIN = os.path.join(ART, 'keeplogin.png')
ICONCONTACT = os.path.join(ART, 'information.png')
ICONSETTINGS = os.path.join(ART, 'settings.png')
# Hide the section separators 'Yes' or 'No'
HIDESPACERS = 'No'
# Character used in separator
#SPACER = '♠'
SPACER = '<->'

# You can edit these however you want, just make sure that you have a %s in each of the
# THEME's so it grabs the text from the menu item
#COLOR1 = 'limegreen'
#COLOR1 = 'blueviolet'
#COLOR1 = 'orchid'ndigo
#COLOR1 = 'darkorchid'
#COLOR13 = 'dodgerblue'
COLOR1 = 'cyan'
COLOR2 = 'white'
COLOR3 = 'orange'
COLOR4 = 'turquoise'
COLOR5 = 'yellowgreen'
# Primary menu items   / {0} is the menu item and is required
THEME1 = u'[COLOR {color1}][COLOR {color1}][B]-[/B][/COLOR][COLOR {color2}][B][/B][COLOR {color1}][/COLOR] [COLOR {color2}]{{}}[/COLOR]'.format(color1=COLOR1, color2=COLOR2, color3=COLOR3, color4=COLOR4, color5=COLOR5)
# Build Names          / {0} is the menu item and is required
THEME2 = u'[COLOR {color1}]{{}}[/COLOR]'.format(color1=COLOR3)
# Alternate items      / {0} is the menu item and is required
THEME3 = u'[COLOR {color1}]{{}}[/COLOR]'.format(color1=COLOR1)
# Current Build Header / {0} is the menu item and is required
THEME4 = u'[COLOR {color1}][B]Build Actual:[/B][/COLOR] [COLOR {color2}]{{}}[/COLOR]'.format(color1=COLOR1, color2=COLOR2, color3=COLOR3, color4=COLOR4, color5=COLOR5)
# Current Theme Header / {0} is the menu item and is required
THEME5 = u'[COLOR {color1}][B]Parche Actual:[/B][/COLOR] [COLOR {color2}]{{}}[/COLOR]'.format(color1=COLOR1, color2=COLOR2, color3=COLOR3, color4=COLOR4, color5=COLOR5)
# Current Theme Header / {0} is the menu item and is required
THEME6 = u'[COLOR {color1}]{{}}[/COLOR]'.format(color1=COLOR4)
# Current Theme Header / {0} is the menu item and is required
THEME7 = u'[COLOR {color1}]{{}}[/COLOR]'.format(color1=COLOR5)

# Message for Contact Page
# Enable 'Contact' menu item 'Yes' hide or 'No' dont hide
HIDECONTACT = 'No'
# You can add \n to do line breaks
CONTACT = 'Gracias por elegir [COLOR azure]TVBAN_MATNEXOM.[/COLOR]\n\nContáctenos en el Grupo Telegram [COLOR white]https://t.me/+andTvban[/COLOR]'
# Images used for the contact window.  http:// for default icon and fanart
CONTACTICON = os.path.join(ART, 'qricon.png')
CONTACTFANART = 'http://'
#########################################################

#########################################################
#        Auto Update For Those With No Repo             #
#########################################################
# Enable Auto Update 'Yes' or 'No'
AUTOUPDATE = 'Yes'
# Url to wizard version
BUILDFILE = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/buildfiles/builds.txt' 
#########################################################

#########################################################
#        Auto Install Repo If Not Installed             #
#########################################################
# Enable Auto Install 'Yes' or 'No'
AUTOINSTALL = 'Yes'
# Addon ID for the repository
REPOID = 'repository.andtvban'
# Url to Addons.xml file in your repo folder(this is so we can get the latest version)
REPOADDONXML = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/piers/zips/addons.xml'
# Url to folder zip is located in
REPOZIPURL = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/piers/zips/repository.andtvban/'
#########################################################

#########################################################
#        Notification Window                            #
#########################################################
# Enable Notification screen Yes or No
ENABLE = 'Yes'
# Url to notification file
NOTIFICATION = 'https://raw.githubusercontent.com/tvbandroid/repositorio.tvbandroid/master/buildfiles/tvban/Notify.txt'
# Use either 'Text' or 'Image'
HEADERTYPE = 'Image'
# Font size of header
FONTHEADER = ''
HEADERMESSAGE = '[COLOR azure][B]TVBAN[/B][/COLOR] [COLOR tan][B]WIZARD[/B][/COLOR]'
# url to image if using Image 424x180
HEADERIMAGE = 'https://i.imgur.com/u9Jzrxi.png'
# Font for Notification Window
FONTSETTINGS = ''
# Background for Notification Window
BACKGROUND = 'https://i.imgur.com/0ciyvn4.png'
#########################################################
