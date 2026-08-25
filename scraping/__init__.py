class SessionExpired(Exception):
    """Levée quand un portail redemande une connexion (identifiants/2FA) au lieu de servir les données.

    Ne jamais tenter de contourner (pas de saisie auto d'identifiants/2FA) : l'appelant
    doit simplement signaler qu'une reconnexion manuelle est nécessaire (icône rouge,
    email/page qui l'indiquent).
    """
