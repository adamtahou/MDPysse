[app]

title = MDPysse
package.name = crypytepwdgen
package.domain = org.crypyte

source.dir = .
source.include_exts = py,kv,png,jpg,ttf

version = 1.0.0

requirements=python3==3.11.0,kivy==2.3.0,kivymd==1.2.0

orientation = portrait
fullscreen = 0

# Aucune permission Android nécessaire : pas d'accès réseau, pas de
# stockage externe (l'historique vit dans le dossier privé de l'appli,
# App.user_data_dir), pas de caméra ni de contacts.
android.permissions =

android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True

p4a.branch = 2024.1.21

[buildozer]

log_level = 2
warn_on_root = 1
