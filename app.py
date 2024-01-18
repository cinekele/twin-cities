import os
import sys
import time
import urllib.parse
from dash import Dash, dcc, html, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_daq as daq

from grapher.twin_cities_graph import TwinCitiesGraph
from wikidata import queries as q
from wikidata.publish import Publisher

from layout_helper import run_standalone_app

def header_colors():
    return {
        'bg_color': '#0C4142',
        'font_color': 'white',
    }


def load_graph() -> TwinCitiesGraph:
    st = time.perf_counter()
    g = TwinCitiesGraph()
    g.load("twin_cities.ttl")
    print(f"Loaded graph in {time.perf_counter() - st:0.2f} seconds")
    return g


graph: TwinCitiesGraph | None = None


def load_cities() -> list[dict[str, str]]:
    # List of city URLs for the dropdown
    st = time.perf_counter()
    cities = graph.get_cities()
    print(f"Got city URLs in {time.perf_counter() - st:0.2f} seconds")
    return [{"label": city["name"] + ', ' + city["country"], "value": city["url"]} for city in cities]


city_urls: list[dict[str, str]] = []


def load_twins_wikidata(city_url: str) -> list[dict[str, str | list[dict[str, str]]]]:
    st = time.perf_counter()
    raw = sorted(q.get_wikidata_twin_data(city_url), key=lambda x: x['targetLabel'])
    print(f"Ran query (wikidata) in {time.perf_counter() - st:0.2f} seconds")
    # remap keys
    data_wikidata = []
    for i in range(len(raw)):
        raw[i]['url'] = urllib.parse.unquote(raw[i].pop('targetUrl'))
        raw[i]['name'] = raw[i].pop('targetLabel')

        if i > 0 and raw[i]['targetId'] == raw[i - 1]['targetId'] and 'referenceUrl' in raw[i]:
            data_wikidata[-1]['references'].append(raw[i]['referenceUrl'])
        else:
            data_wikidata.append({**raw[i]})
            data_wikidata[-1]['references'] = []
            if 'referenceUrl' in data_wikidata[-1]:
                data_wikidata[-1]['references'].append({
                    "url": data_wikidata[-1].pop('referenceUrl'),
                    "name": data_wikidata[-1].pop('referenceName') if 'referenceName' in data_wikidata[-1] else None,
                    "publisher": data_wikidata[-1].pop('referencePublisher') if 'referencePublisher' in data_wikidata[
                        -1] else None,
                })
    return data_wikidata


def load_twins_wikipedia(city_url: str) -> list[dict[str, str]]:
    st = time.perf_counter()
    data_wikipedia = sorted(graph.get_twins(city_url), key=lambda x: x['name'])
    print(f"Ran query (wikipedia) in {time.perf_counter() - st:0.2f} seconds")
    return data_wikipedia


def align_twins(data_wikidata: list[dict[str, str]], data_wikipedia: list[dict[str, str]]) -> list[
    dict[str, dict[str, str]]]:
    twins = []
    i = 0
    j = 0
    while i < len(data_wikidata) and j < len(data_wikipedia):
        if data_wikidata[i]['url'] != data_wikipedia[j]['url']:
            if data_wikidata[i]['name'] == data_wikipedia[j]['name']:
                twins.append({
                    "wikidata": data_wikidata[i],
                    "wikipedia": data_wikipedia[j]
                })
                i += 1
                j += 1
            else:
                if data_wikidata[i]['url'] < data_wikipedia[j]['url']:
                    twins.append({
                        "wikidata": data_wikidata[i],
                        "wikipedia": None
                    })
                    i += 1
                elif data_wikidata[i]['url'] > data_wikipedia[j]['url']:
                    twins.append({
                        "wikidata": None,
                        "wikipedia": data_wikipedia[j]
                    })
                    j += 1
        else:
            twins.append({
                "wikidata": data_wikidata[i],
                "wikipedia": data_wikipedia[j]
            })
            i += 1
            j += 1
    while i < len(data_wikidata):
        twins.append({
            "wikidata": data_wikidata[i],
            "wikipedia": None
        })
        i += 1
    while j < len(data_wikipedia):
        twins.append({
            "wikidata": None,
            "wikipedia": data_wikipedia[j]
        })
        j += 1
    return twins


twins_details: list[dict[str, dict[str, str]]] = []
twins_names: list[dict[str, str]] = []
references_wikipedia: list[dict[str, str]] = []
details_names = ["name", "url"]


def setup():
    global graph, city_urls
    graph = load_graph()
    city_urls = load_cities()


table_right_config = dict(
    markdown_options={'html': True},
    columns=[{"name": "Property", "id": "property"},
             {"name": "Wikipedia", "id": "wikipedia", "presentation": "markdown", "type": "text"},
             {"name": "Wikidata", "id": "wikidata", "presentation": "markdown", "type": "text"}],
    style_cell={'textAlign': 'left'}, # , 'width': '33%'
    style_data={'whiteSpace': 'normal'}, #, 'height': 'auto'
    style_table={'margin-top': '10px'}, # , 'width': '100%'
    style_data_conditional=[
        {
            'if': {
                'state': 'selected',
            },
            'backgroundColor': 'rgba(75, 75, 255, 0.2)',
            'border': '1px solid rgb(75, 75, 255)',
        }
    ],
    css=[{'selector': 'table', 'rule': 'table-layout: fixed'},
         {'selector': '.dash-cell div.dash-cell-value', 'rule': 'overflow-wrap: break-word'},
         {'selector': 'p', 'rule': 'margin: 0'},
         {'selector': 'div.dash-cell-value.cell-markdown', 'rule': 'font-family: monospace'}]
)
EMPTY_VALUE = ""
def layout():
    return html.Div(id='app-body', className='app-body', children=[
            dcc.Store(id='memory'),
            html.Div([
                
            html.Div(className='control-tab two columns', children=[
                html.H4(
                    className='what-is',
                    children='What is Alignment Viewer?'
                ),
                html.P(
                    """
                    This application is going to help to complete
                    information in Wikidata about Twin Cities.
                    """
                ),
                html.P(
                    """
                    It will allow you to compare information from
                    Wikipedia and Wikidata and update Wikidata.
                    
                    First Select Tab XYZ to see the list of twin cities.
                    Then ...
                    """
                ),
                html.P(
                    """
                    Read more about the component here:
                    ...
                    """
                ),
            ]),
            html.Div(id='ten columns', className='', children=[
                dcc.Tabs(
                    id='multiple-tabs', value='what-is',
                    children=[
                        dcc.Tab(
                            label='Twin city comparision',
                            value='twin-list',
                            children=html.Div(className='single-tab', children=[
                                html.Div(className="search-div", children=[
                                    html.Div(className="dropdown-div nine columns", children=[
                                        dcc.Dropdown(id='city-url', className='', options=[], placeholder='Select a city'),
                                    ]),
                                    html.Button('Run Query', id='run-button', className='three columns'),
                                ]),
                                daq.BooleanSwitch(label="Show only twin cities from Wikipedia", id='hide-switch', on=False,
                                                labelPosition='top', style={'margin-top': '10px', 'margin-bottom': '10px'}),
                                html.Div(id='output-table', className='table twin-cities-table', children=[
                                    dash_table.DataTable(id='dash-table',
                                                        columns=[{"name": i, "id": i.lower()} for i in ["Wikipedia", "Wikidata"]],
                                                        fixed_rows={'headers': True},
                                                        style_cell={'textAlign': 'left'}, # , 'width': '50%'
                                                        style_data_conditional=[
                                                            {
                                                                'if': {
                                                                    'filter_query': '{wikipedia} is nil',
                                                                    'column_id': 'wikipedia',
                                                                },
                                                                'backgroundColor': 'rgb(255, 175, 175, 0.5)',
                                                            },
                                                            {
                                                                'if': {
                                                                    'filter_query': '{wikidata} is nil',
                                                                    'column_id': 'wikidata',
                                                                },
                                                                'backgroundColor': 'rgb(175, 255, 175, 0.5)',
                                                            },
                                                            {
                                                                'if': {
                                                                    'filter_query': '!({wikipedia} is nil) && {wikidata} is nil',
                                                                    'column_id': 'wikipedia',
                                                                },
                                                                'backgroundColor': 'rgba(255, 175, 175, 0.5)',
                                                            },
                                                            {
                                                                'if': {
                                                                    'state': 'selected',
                                                                },
                                                                'backgroundColor': 'rgba(75, 75, 255, 0.2)',
                                                                'border': '1px solid rgb(75, 75, 255)',
                                                            }
                                                        ]),
                                ], style={'margin-top': '10px', 'margin-bottom': '10px', 'max-height': '500px', 'overflow': 'auto'}),
                                # style={'height': '100%', 'width': '40%', 'display': 'inline-block', 'vertical-align': 'top'}
                            ])
                        )
                        ]
                    )
                ]),
            
        ]),
        html.Div([
            dash_table.DataTable(id='dash-table-details',
                                **table_right_config),
            dash_table.DataTable(id='dash-table-refs',
                                **table_right_config),
            html.Button('Update Wikidata', id='update-button', hidden=True, disabled=False,
                        style={'margin-top': '10px', 'margin-bottom': '10px'}),
            dbc.Alert("ERROR !!! Something went wrong.", id='error_alert', is_open=False, fade=True, dismissable=True,
                    style={'margin-top': '10px', 'margin-bottom': '10px'}, color='danger'),
            dbc.Alert("Update performed successfully !!!", id='success_alert', is_open=False, fade=True, dismissable=True,
                    style={'margin-top': '10px', 'margin-bottom': '10px'}, color='success')
        ],
            style={'width': '50%', 'display': 'inline-block', 'margin-left': '5%'}
        )
        ],
        #style={'height': '100%', 'width': '100%'}
    )


def callbacks(_app: Dash):

    @_app.callback(
        Output('update-button', 'disabled', allow_duplicate=True),
        Output('memory', 'data'),
        Input('update-button', 'n_clicks'),
        State('city-url', 'value'),
        State('dash-table', 'active_cell'),
        prevent_initial_call=True,
    )
    def query(n_clicks, city_url, active_cell):
        if n_clicks is None or city_url is None or active_cell is None:
            return False

        source_id = None
        for details in twins_details:
            if details['wikidata'] is not None:
                source_id = details['wikidata']['sourceId']
                break

        row = active_cell['row']
        details = twins_details[row]

        update_object = {
            "sourceUrl": city_url,
            "sourceId": source_id,
            "twin": {
                **details['wikipedia'],
                "references": references_wikipedia
            }
        }
        try:
            res = publisher.update(update_object)
            return True, res
        except Exception as e:
            message = str(e)
            return True, message

    @_app.callback(
        [Output('error_alert', 'is_open'), Output('error_alert', 'children')],
        Input('memory', 'data'),
        prevent_initial_call=True,
    )
    def show_error_alert(data):
        if isinstance(data, str):
            return True, data
        return False, ""


    @_app.callback(
        Output('success_alert', 'is_open'),
        Output('success_alert', 'children'),
        Input('memory', 'data'),
        prevent_initial_call=True
    )
    def show_success_alert(data):
        if isinstance(data, bool) and data:
            return True, "Updated successfully"
        return False, ""


    @_app.callback(
        Output("city-url", "options"),
        Input("city-url", "search_value")
    )
    def update_options(search_value):
        if not search_value or len(search_value) < 3:
            # return [] # either clear previous search results or keep old ones
            raise PreventUpdate
        options = city_urls
        st = time.perf_counter()
        out = [o for o in options if search_value.lower() in o["label"].lower()][:100]
        print(f"Filtered options in {time.perf_counter() - st:0.2f} seconds")
        return out


    @_app.callback(
        Output('dash-table-refs', 'data', allow_duplicate=True),
        Input('dash-table-details', 'active_cell'),
        State('dash-table', 'active_cell'),
        prevent_initial_call=True,
    )
    def update_refs(active_cell, active_cell_main):
        if active_cell is None or active_cell_main is None:
            return None

        row_main = active_cell_main['row']
        row = active_cell['row']
        details = twins_details[row_main]
        if row >= len(details_names):
            if row - len(details_names) < len(references_wikipedia):
                reference = references_wikipedia[row - len(details_names)]
                table = []
                for key, value in reference.items():
                    if value is None:
                        continue
                    table.append({
                        "property": key,
                        "wikipedia": value if key != "url" else f"<a href='{value}' target='_blank' >{value}</a>",
                        "wikidata": EMPTY_VALUE
                    })
                return table
            else:
                reference = details['wikidata']['references'][row - len(details_names) - len(references_wikipedia)]
                table = []
                for key, value in reference.items():
                    if value is None:
                        continue
                    table.append({
                        "property": key,
                        "wikipedia": EMPTY_VALUE,
                        "wikidata": value if key != "url" else f"<a href='{value}' target='_blank' >{value}</a>"
                    })
                return table
        return None


    @_app.callback(
        Output('dash-table-details', 'data', allow_duplicate=True),
        Output('dash-table-refs', 'data', allow_duplicate=True),
        Output('update-button', 'hidden', allow_duplicate=True),
        Output('update-button', 'disabled', allow_duplicate=True),
        Input('dash-table', 'active_cell'),
        State('city-url', 'value'),
        prevent_initial_call=True,
    )
    def update_details(active_cell, city_url):
        if active_cell is None:
            return None, None, True, False

        row = active_cell['row']
        details = twins_details[row]
        table = []
        for details_name in details_names:
            field_wikipedia = details['wikipedia'][details_name] if details['wikipedia'] is not None else None
            field_wikidata = details['wikidata'][details_name] if details['wikidata'] is not None else None
            if details_name == "url":
                field_wikipedia = f"<a href='{field_wikipedia}' target='_blank' >{field_wikipedia}</a>" if field_wikipedia is not None else EMPTY_VALUE
                field_wikidata = f"<a href='{field_wikidata}' target='_blank' >{field_wikidata}</a>" if field_wikidata is not None else EMPTY_VALUE
            table.append({
                "property": details_name,
                "wikipedia": field_wikipedia if field_wikipedia is not None else EMPTY_VALUE,
                "wikidata": field_wikidata if field_wikidata is not None else EMPTY_VALUE
            })
        global references_wikipedia
        if details['wikipedia'] is not None:
            references_wikipedia = graph.get_references(city_url, details['wikipedia']['url'])
            for reference in references_wikipedia:
                table.append({
                    "property": "reference",

                    "wikipedia": reference['name'],
                    "wikidata": EMPTY_VALUE
                })
        else:
            references_wikipedia = []
        if details['wikidata'] is not None:
            for reference in details['wikidata']['references']:
                table.append({
                    "property": "reference",
                    "wikipedia": EMPTY_VALUE,
                    "wikidata": reference['name'] if reference['name'] is not None else reference['url']
                })

        button_hidden = True
        if twins_names[row]['wikipedia'] is not None and twins_names[row]['wikidata'] is None:
            button_hidden = False
        return table, None, button_hidden, False


    @_app.callback(
        Output('dash-table', 'data', allow_duplicate=True),
        Input('hide-switch', 'on'),
        prevent_initial_call=True,
    )
    def update_table_hide(on):
        global twins_names
        twins_names = []
        for result in twins_details:
            if on and result['wikidata'] is not None:
                continue
            twins_names.append({"wikipedia": result['wikipedia']['name'] if result['wikipedia'] is not None else None,
                                "wikidata": result['wikidata']['name'] if result['wikidata'] is not None else None})
        return twins_names


    @_app.callback(
        Output('dash-table', 'data'),
        Output('dash-table-details', 'data'),
        Output('dash-table-refs', 'data'),
        Output('hide-switch', 'on'),
        Output('update-button', 'hidden'),
        Output('update-button', 'disabled'),
        Input('run-button', 'n_clicks'),
        State('city-url', 'value'),
        prevent_initial_call=True,
    )
    def update_table(n_clicks, city_url):
        if n_clicks is None:
            return None, None, None, False, True, False  # Not clicked yet

        data_wikidata = load_twins_wikidata(city_url)
        data_wikipedia = load_twins_wikipedia(city_url)

        global twins_details, twins_names
        twins_details = align_twins(data_wikidata, data_wikipedia)
        twins_names = []

        for result in twins_details:
            twins_names.append({"wikipedia": result['wikipedia']['name'] if result['wikipedia'] is not None else None,
                                "wikidata": result['wikidata']['name'] if result['wikidata'] is not None else None})
        return twins_names, None, None, False, True, False


app = run_standalone_app(layout, callbacks, header_colors, __file__)
server = app.server
publisher = Publisher()

if __name__ == '__main__':
    setup()
    app.run_server(debug=True)
