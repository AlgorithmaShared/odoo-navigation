{
    "name": "Algorithma Navigation",
    "version": "18.0.1.3.0",
    "summary": "Optional app groups and direct app links for MuK AppsBar",
    "category": "Productivity",
    "author": "Algorithma Informatik GmbH",
    "license": "LGPL-3",
    "depends": ["muk_web_appsbar"],
    "data": [
        "security/ir.model.access.csv",
        "data/navigation_groups.xml",
        "views/navigation_group_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "algorithma_navigation/static/src/**/*.js",
            "algorithma_navigation/static/src/**/*.xml",
            "algorithma_navigation/static/src/**/*.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
