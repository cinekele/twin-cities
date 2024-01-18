import base64
import os

import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc

def run_standalone_app(
        layout,
        callbacks,
        app_name,
        header_colors,
        filename
):
    """Run app (app.py) as standalone app."""
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    app.scripts.config.serve_locally = True
    # Handle callback to component with id "fullband-switch"
    app.config['suppress_callback_exceptions'] = True

    # Get all information from filename
    app_name = os.getenv('DASH_APP_NAME', app_name)
    if app_name == '':
        app_name = os.path.basename(os.path.dirname(filename))
    app_name = app_name.replace('dash-', '')

    app_title = "{}".format(app_name.replace('-', ' ').title())

    # Assign layout
    app.layout = app_page_layout(
        page_layout=layout(),
        app_title=app_title,
        app_name=app_name,
        standalone=True,
        **header_colors()
    )

    # Register all callbacks
    callbacks(app)

    # return app object
    return app


def app_page_layout(page_layout,
                    app_title="Twin Cities",
                    app_name="",
                    light_logo=True,
                    standalone=False,
                    bg_color="#506784",
                    font_color="#F3F6FA"):
    return html.Div(
        id='main_page',
        children=[
            dcc.Location(id='url', refresh=False),
            html.Div(
                id='app-page-header',
                children=[
                    # html.A(
                    #     id='dashbio-logo', children=[
                    #         html.Img(
                    #             src='data:image/png;base64,{}'.format(
                    #                 base64.b64encode(
                    #                     open(
                    #                         './assets/plotly-dash-logo.png', 'rb'
                    #                     ).read()
                    #                 ).decode()
                    #         ),
                    #     )],
                    #     href="/Portal" if standalone else "/dash-bio"
                    # ),
                    html.H2(
                        app_title, style={'padding-left': '10px'}
                    ),

                    html.A(
                        id='gh-link',
                        children=[
                            'View on GitHub'
                        ],
                        href="http://github.com/cinekele/twin-cities/",
                        style={'color': 'white' if light_logo else 'black',
                               'border': 'solid 1px white' if light_logo else 'solid 1px black'}
                    ),

                    html.Img(
                        src='data:image/png;base64,{}'.format(
                            base64.b64encode(
                                open(
                                    './assets/GitHub-Mark-{}64px.png'.format(
                                        'Light-' if light_logo else ''
                                    ),
                                    'rb'
                                ).read()
                            ).decode()
                        )
                    )
                ],
                style={
                    'background': bg_color,
                    'color': font_color,
                }
            ),
            html.Div(
                id='app-page-content',
                children=page_layout
            )
        ],
    )