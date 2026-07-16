{
    'name': 'MLKGP Migration',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Scripts de migration pour MLKGP',
    'description': """
        Module technique contenant les scripts de migration pour MLKGP
    """,
    'author': 'PERROTTECH',
    'depends': ['base'],
    'installable': True,
    'auto_install': True,  # S'installe automatiquement
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
