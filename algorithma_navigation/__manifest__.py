{
    "name": "Algorithma Navigation",
    "version": "20.0.1.3.0",
    "summary": "Optional app groups and direct app links for MuK AppsBar",
    "category": "Productivity",
    "author": "Algorithma Informatik GmbH",
    "license": "LGPL-3",
    "depends": ["muk_web_appsbar"],
    "data": [
        "security/ir.access.csv",
        "data/navigation_groups.xml",
        "views/navigation_group_views.xml",
    ],
    "assets": {
        # Default sidebar colours: must follow MuK's own variables to see their values.
        "web._assets_primary_variables": [
            (
                "after",
                "muk_web_appsbar/static/src/webclient/appsbar/variables.scss",
                "algorithma_navigation/static/src/scss/primary_variables.scss",
            ),
        ],
        "web.assets_backend": [
            "algorithma_navigation/static/src/**/*.js",
            "algorithma_navigation/static/src/**/*.xml",
            # Top level only: static/src/scss/ holds the primary variables loaded above.
            # (A "remove" here would also drop them from the included variables bundle.)
            "algorithma_navigation/static/src/*.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
