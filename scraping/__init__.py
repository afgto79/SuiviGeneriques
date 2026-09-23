class SessionExpired(Exception):
    """Levée quand un portail redemande une connexion (identifiants/2FA) au lieu de servir les données.

    Ne jamais tenter de contourner (pas de saisie auto d'identifiants/2FA) : l'appelant
    doit simplement signaler qu'une reconnexion manuelle est nécessaire (icône rouge,
    email/page qui l'indiquent).
    """


class DonneesPerimees(Exception):
    """Levée quand un portail répond bien, mais avec des données trop anciennes ou d'un
    autre mois que celui en cours (ex. réponse servie par le cache HTTP, ou portail pas
    encore basculé sur le nouveau mois). On signale l'erreur plutôt que d'afficher un
    montant faux sans le dire.
    """
