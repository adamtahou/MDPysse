# -*- coding: utf-8 -*-
"""
main.py — CryPyte PwdGen : générateur de mots de passe déterministe,
version Android autonome (Kivy/KivyMD 1.2.0).
"""

import threading

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.list import TwoLineListItem

import crypto_utils
import storage

# ⚠️ Toutes les interactions UI vers Python se font par passage de valeurs
# directement dans le KV (on_release: app.methode(widget.text, ...))
# plutôt que par self.root.ids dans le Python — évite les problèmes de
# timing liés à la disponibilité de self.root au moment du callback.
KV = """
MDBoxLayout:
    orientation: "vertical"

    MDTopAppBar:
        title: "CryPyte — Générateur de mots de passe"
        elevation: 4

    ScrollView:
        do_scroll_x: False

        MDBoxLayout:
            orientation: "vertical"
            padding: "20dp", "24dp", "20dp", "16dp"
            spacing: "14dp"
            size_hint_y: None
            height: self.minimum_height

            # ── Génération ──────────────────────────────────────────────────

            MDLabel:
                text: "Paramètres"
                font_style: "H6"
                size_hint_y: None
                height: self.texture_size[1] + dp(8)

            MDTextField:
                id: maitre
                hint_text: "Mot de passe maître"
                helper_text: "Jamais stocké — utilisé uniquement pendant le calcul"
                helper_text_mode: "persistent"
                password: True
                mode: "rectangle"
                size_hint_y: None
                height: "72dp"

            MDTextField:
                id: site
                hint_text: "Nom du site (sans espace)"
                mode: "rectangle"
                size_hint_y: None
                height: "56dp"
                on_text: app.on_site_text_changed(self.text)

            MDTextField:
                id: n_field
                hint_text: "Nombre de leaks (n)"
                input_filter: "int"
                text: "0"
                mode: "rectangle"
                size_hint_y: None
                height: "56dp"

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: "54dp"
                spacing: "4dp"

                MDLabel:
                    id: longueur_label
                    text: "Longueur : 16"
                    size_hint_y: None
                    height: "22dp"

                MDSlider:
                    id: longueur_slider
                    min: 8
                    max: 64
                    value: 16
                    step: 1
                    size_hint_y: None
                    height: "28dp"
                    on_value: longueur_label.text = f"Longueur : {int(self.value)}"

            MDRaisedButton:
                text: "Générer"
                pos_hint: {"center_x": 0.5}
                size_hint_x: 0.6
                size_hint_y: None
                height: "48dp"
                # Passage direct des valeurs : évite self.root.ids dans le Python
                on_release: app.on_generate_pressed(maitre.text, site.text, n_field.text, int(longueur_slider.value))

            MDBoxLayout:
                orientation: "horizontal"
                size_hint_y: None
                height: "56dp"
                spacing: "8dp"

                MDTextField:
                    id: resultat
                    hint_text: "Mot de passe généré"
                    readonly: True
                    mode: "rectangle"
                    size_hint_x: 1

                MDRaisedButton:
                    text: "Copier"
                    size_hint_x: None
                    width: "90dp"
                    on_release: app.copier(resultat.text)

            MDLabel:
                id: status_label
                text: ""
                theme_text_color: "Secondary"
                size_hint_y: None
                height: "24dp"

            MDSeparator:
                size_hint_y: None
                height: "1dp"

            # ── Historique ──────────────────────────────────────────────────

            MDLabel:
                text: "Historique des sites"
                font_style: "H6"
                size_hint_y: None
                height: self.texture_size[1] + dp(8)

            MDTextField:
                id: recherche
                hint_text: "Rechercher un site"
                mode: "rectangle"
                size_hint_y: None
                height: "56dp"
                on_text: app.on_search_changed(self.text)

            MDList:
                id: history_list
                size_hint_y: None
                height: self.minimum_height
"""


class CryptePwdGenApp(MDApp):
    """Application Kivy/KivyMD — générateur de mots de passe déterministe."""

    def build(self):
        self.title = "CryPyte — Générateur de mots de passe"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self._historique = []
        self._dernier_copie = None
        self._dialog = None
        self._ids = None   # Sera rempli dans on_start, une fois le KV construit
        return Builder.load_string(KV)

    def on_start(self):
        # On cache les références aux widgets ICI, pas dans build() —
        # à ce stade self.root est garanti non-None.
        self._ids = self.root.ids
        self._historique = storage.lire_historique(self.user_data_dir)
        self._rafraichir_liste()

    # ── SAISIE ────────────────────────────────────────────────────────────

    def on_site_text_changed(self, site_text):
        """Pré-remplit n si le site est déjà dans l'historique."""
        if self._ids is None:
            return
        site_text = site_text.strip()
        for s, n in self._historique:
            if s == site_text:
                self._ids.n_field.text = str(n)
                break

    def on_search_changed(self, terme):
        self._rafraichir_liste(terme)

    # ── HISTORIQUE ────────────────────────────────────────────────────────

    def _rafraichir_liste(self, terme=""):
        if self._ids is None:
            return
        history_list = self._ids.history_list
        history_list.clear_widgets()
        for site, n in sorted(self._historique):
            if storage.correspond(site, terme):
                item = TwoLineListItem(
                    text=site,
                    secondary_text=f"n = {n}",
                    on_release=lambda it, s=site, nn=n: self._selectionner_site(s, nn),
                )
                history_list.add_widget(item)

    def _selectionner_site(self, site, n):
        if self._ids is None:
            return
        self._ids.site.text = site
        self._ids.n_field.text = str(n)

    # ── GÉNÉRATION ────────────────────────────────────────────────────────

    def on_generate_pressed(self, maitre, site, n_text, longueur):
        """
        Reçoit les valeurs directement depuis le KV — pas de self.root.ids
        ici, ce qui évite tout problème de timing.
        """
        site = site.strip()

        if not maitre or not site:
            self._status("Mot de passe maître et nom de site requis.")
            return
        if " " in site:
            self._status("Le nom du site ne peut pas contenir d'espace.")
            return
        if len(maitre) < 4:
            self._status("Le mot de passe maître doit faire au moins 4 caractères.")
            return
        try:
            n = int(n_text) if n_text else 0
        except ValueError:
            self._status("n doit être un nombre entier.")
            return

        n_existant = dict(self._historique).get(site)
        if n_existant is not None and n_existant != n:
            self._demander_conflit(site, n_existant, n, maitre, longueur)
        else:
            self._lancer_generation(site, n, maitre, longueur)

    def _demander_conflit(self, site, n_stocke, n_saisi, maitre, longueur):
        def repondre(garder_saisie):
            self._dialog.dismiss()
            n_final = n_saisi if garder_saisie else n_stocke
            if self._ids:
                self._ids.n_field.text = str(n_final)
            self._lancer_generation(site, n_final, maitre, longueur)

        self._dialog = MDDialog(
            title="Différence détectée",
            text=(
                f"'{site}' a déjà n = {n_stocke} dans l'historique, "
                f"vous avez saisi n = {n_saisi}.\n"
                f"Quelle valeur utiliser ?"
            ),
            buttons=[
                MDFlatButton(
                    text=f"Garder {n_stocke}",
                    on_release=lambda *_: repondre(False)
                ),
                MDFlatButton(
                    text=f"Utiliser {n_saisi}",
                    on_release=lambda *_: repondre(True)
                ),
            ],
        )
        self._dialog.open()

    def _lancer_generation(self, site, n, maitre, longueur):
        self._status("Dérivation en cours…")
        if self._ids:
            self._ids.resultat.text = ""

        def travail():
            dk  = crypto_utils.deriver_cle_generateur(maitre, site, n)
            mdp = crypto_utils.construire_mot_de_passe(dk, site, longueur)
            Clock.schedule_once(lambda dt: self._on_genere(site, n, mdp), 0)

        threading.Thread(target=travail, daemon=True).start()

    def _on_genere(self, site, n, mot_de_passe):
        if self._ids:
            self._ids.resultat.text = mot_de_passe

        # Mise à jour historique (site + n uniquement — jamais le mot de passe)
        entrees = dict(self._historique)
        entrees[site] = n
        self._historique = list(entrees.items())
        storage.ecrire_historique(self._historique, self.user_data_dir)

        terme = self._ids.recherche.text if self._ids else ""
        self._rafraichir_liste(terme)

        self.copier(mot_de_passe)

    # ── PRESSE-PAPIERS ────────────────────────────────────────────────────

    def copier(self, mot_de_passe):
        """Copie le mot de passe dans le presse-papiers. Appelée depuis le KV."""
        if not mot_de_passe:
            self._status("Rien à copier — générez d'abord un mot de passe.")
            return
        Clipboard.copy(mot_de_passe)
        self._status("✓ Copié dans le presse-papiers.")

    # ── DIVERS ────────────────────────────────────────────────────────────

    def _status(self, message):
        if self._ids:
            self._ids.status_label.text = message


if __name__ == "__main__":
    CryptePwdGenApp().run()
