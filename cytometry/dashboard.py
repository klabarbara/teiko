import os
import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, no_update, dash_table
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine
from cytometry.db import init_db
from cytometry.analysis import (
    test_significant_populations,
    get_baseline_samples,
    summarize_baseline
)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///cytometry.db")
engine = create_engine(DATABASE_URL, echo=False)

# Ensure tables exist before any read_sql calls
init_db(DATABASE_URL)


sample_list = pd.read_sql(
    "SELECT DISTINCT sample_id FROM samples ORDER BY sample_id", engine
)["sample_id"].tolist()

# our pagination relative frequency query (see readme for more info) note the limit/offset
REL_FREQ_SQL = """
WITH rf AS (
  SELECT
    c.sample_id AS sample,
    SUM(c.count) OVER (PARTITION BY c.sample_id) AS total_count,
    c.population,
    c.count,
    ROUND(c.count*1.0/SUM(c.count) OVER (PARTITION BY c.sample_id)*100,2) AS percentage
  FROM cell_counts c
)
SELECT * FROM rf
ORDER BY sample, population
LIMIT :limit OFFSET :offset;
"""

# fetching baseline subset features and deduping
df_cols = pd.read_sql(
    "SELECT DISTINCT condition, treatment, sample_type, time_from_treatment_start FROM samples", engine
)
condition_options = df_cols["condition"].unique().tolist()
treatment_options = df_cols["treatment"].unique().tolist()
sample_type_options = df_cols["sample_type"].unique().tolist()
time_point_options = sorted(df_cols["time_from_treatment_start"].unique().tolist())

# default values per Part 4
DEFAULT_COND = "melanoma"
DEFAULT_TREAT = "miraclib"
DEFAULT_STYPE = "PBMC"
DEFAULT_TIME = 0

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True
)
server = app.server

tabs = dcc.Tabs(id="tabs", value="tab-overview", children=[
    dcc.Tab(label="Overview", value="tab-overview"),
    dcc.Tab(label="Responder Analysis", value="tab-responder"),
    dcc.Tab(label="Significance", value="tab-significance"),
    dcc.Tab(label="Baseline Subset", value="tab-baseline"),
])

title = html.H2("Loblaw Cytometry Trial Dashboard")
app.layout = dbc.Container([
    dbc.Row(dbc.Col(title, width=12), className="mt-4 mb-2"),
    dbc.Row(dbc.Col(tabs, width=12)),
    dbc.Row(dbc.Col(html.Div(id="tab-content"), width=12)),
], fluid=True)

def overview_layout():
    table = dash_table.DataTable(
        id="overview-table",
        columns=[
            {"name": "Sample", "id": "sample"},
            {"name": "Total Count", "id": "total_count"},
            {"name": "Population", "id": "population"},
            {"name": "Count", "id": "count"},
            {"name": "Percentage", "id": "percentage"},
        ],
        page_action="custom",
        page_current=0,
        page_size=10,
        row_selectable="single",
        style_as_list_view=True,
        style_header={"backgroundColor":"#f8f9fa","fontWeight":"bold"},
        style_cell={"padding":"5px","textAlign":"center"},
    )
    page_indicator = html.Div(id='page-indicator', style={'textAlign':'right','marginTop':'10px'})
    search = html.Div([
        dcc.Input(id='sample-search', type='text', placeholder='Enter sample ID...'),
        html.Button('Go', id='search-button', n_clicks=0, style={'marginLeft':'5px'})
    ], style={'marginTop':'10px','marginBottom':'5px'})
    instructions = html.P("Select a sample to visualize relative population frequencies below.", style={'fontStyle':'italic'})
    pie = dcc.Graph(id="overview-pie", style={'display':'none'})
    return html.Div([table, page_indicator, search, instructions, pie])

def render_overview():
    return overview_layout()

def render_responder():
    df = pd.read_sql(
        "SELECT c.sample_id AS sample, "
        "SUM(c.count) OVER (PARTITION BY c.sample_id) AS total_count, "
        "c.population, c.count, s.response "
        "FROM cell_counts c JOIN samples s ON s.sample_id=c.sample_id "
        "WHERE s.condition='melanoma' AND s.treatment='miraclib' AND s.sample_type='PBMC'",
        engine
    )
    df['percentage'] = df['count'] / df['total_count'] * 100

    df['response_str'] = df['response'].map({1: 'responder', True: 'responder', 0: 'non-responder', False: 'non-responder'})
    fig = px.box(
        df, x='population', y='percentage', color='response_str',
        labels={'percentage': 'Percentage (%)', 'response_str': 'Response'},
        title='Responder vs Non-Responder'
    )
    fig.update_layout(xaxis_tickangle=-45)
    return dcc.Graph(figure=fig)

def render_significance():
    stats = test_significant_populations(engine, 'melanoma', 'miraclib')

    columns = [
        {'name': 'Population', 'id': 'population'},
        {'name': 'U-Statistic', 'id': 'u_stat'},
        {'name': 'P-Value', 'id': 'p_value'},
        {'name': 'Significant', 'id': 'significant'},
    ]
    return dash_table.DataTable(
        columns=columns,
        data=stats.to_dict('records'),
        style_as_list_view=True,
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
        style_cell={'padding': '5px', 'textAlign': 'center'},
        style_data_conditional=[
            {'if': {'filter_query': '{significant} = true', 'column_id': 'significant'},
             'backgroundColor': '#D4EDDA', 'color': '#155724'}
        ]
    )

# FYI: little bit of AI help here to get the dropdowns right/quickly
def baseline_layout():
    filters = dbc.Card(
        dbc.CardBody([
            html.H5("Baseline Subset Filters", className="card-title"),
            dbc.Row([dbc.Label('Condition', width=2), dbc.Col(
                dcc.Dropdown(
                    id='base-cond',
                    options=[{'label': c, 'value': c} for c in condition_options],
                    value=DEFAULT_COND
                ), width=4
            )], className='mb-2'),
            dbc.Row([dbc.Label('Treatment', width=2), dbc.Col(
                dcc.Dropdown(
                    id='base-treat',
                    options=[{'label': t, 'value': t} for t in treatment_options],
                    value=DEFAULT_TREAT
                ), width=4
            )], className='mb-2'),
            dbc.Row([dbc.Label('Sample Type', width=2), dbc.Col(
                dcc.Dropdown(
                    id='base-stype',
                    options=[{'label': s, 'value': s} for s in sample_type_options],
                    value=DEFAULT_STYPE
                ), width=4
            )], className='mb-2'),
            dbc.Row([dbc.Label('Time Point', width=2), dbc.Col(
                dcc.Dropdown(
                    id='base-time',
                    options=[{'label': tp, 'value': tp} for tp in time_point_options],
                    value=DEFAULT_TIME
                ), width=4
            )], className='mb-2'),
        ]),
        className='mt-3'
    )
    output = html.Div(id='baseline-output')
    return html.Div([filters, output])

@app.callback(Output('tab-content', 'children'), Input('tabs', 'value'))
def render_tab(tab):
    if tab == 'tab-overview':
        return render_overview()
    elif tab == 'tab-responder':
        return render_responder()
    elif tab == 'tab-significance':
        return render_significance()
    else:
        return baseline_layout()

# callbacks to wire our functions into dash without dealing with events manually
# this is a great reason to use dash. 
@app.callback(
    [Output('overview-table', 'data'), Output('page-indicator', 'children')],
    Input('overview-table', 'page_current'), Input('overview-table', 'page_size')
)
def update_overview(page_current, page_size):
    df = pd.read_sql(REL_FREQ_SQL, engine, params={'limit': page_size, 'offset': page_current * page_size})
    total_pages = (len(sample_list) * 5 + page_size - 1) // page_size
    return df.to_dict('records'), f"Page {page_current+1} of {total_pages}"

@app.callback(
    Output('overview-table', 'page_current'),
    Input('search-button', 'n_clicks'), State('sample-search', 'value'), State('overview-table', 'page_size')
)
def search_page(n, value, page_size):
    if not n or not value or value not in sample_list:
        return no_update
    return (sample_list.index(value) * 5) // page_size

@app.callback(
    [Output('overview-pie', 'figure'), Output('overview-pie', 'style')],
    Input('overview-table', 'selected_rows'), State('overview-table', 'data')
)
def update_pie(selected, rows):
    if not selected:
        return no_update, {'display': 'none'}
    sample = rows[selected[0]]['sample']
    df = pd.read_sql(REL_FREQ_SQL, engine, params={'limit': -1, 'offset': 0})
    df = df[df['sample'] == sample]
    fig = px.pie(df, names='population', values='percentage', title=f'Sample {sample} Composition')
    return fig, {'display': 'block'}

@app.callback(
    Output('baseline-output', 'children'),
    Input('tabs', 'value'),
    Input('base-cond', 'value'), Input('base-treat', 'value'),
    Input('base-stype', 'value'), Input('base-time', 'value')
)
def update_baseline(tab, cond, treat, stype, time_point):
    if tab != 'tab-baseline':
        return no_update
    df = get_baseline_samples(engine, cond, treat, stype, time_point)
    if df.empty:
        return html.P('No baseline samples match the selected filters.')
    proj_counts, resp_counts, sex_counts = summarize_baseline(df)

    # samples/project
    fig1 = px.bar(
        proj_counts,
        x='project', y='num_samples',
        color='project',                           
        title='Samples per Project',
        color_discrete_sequence=px.colors.qualitative.Plotly  # fancy color palette 
    )
    fig1.update_layout(xaxis_title='Project', yaxis_title='Number of Samples')

    # responders vs nornresponders 
    fig2 = px.bar(
        resp_counts,
        x='response', y='num_subjects',
        color='response',                          
        title='Responders vs Non-Responders',
        color_discrete_sequence=['#636EFA', '#EF553B'],  # traditional hex assignment
        category_orders={'response': ['non-responder','responder']}
    )
    fig2.update_layout(xaxis_title='Response', yaxis_title='Number of Subjects')

    # sex distribution
    fig3 = px.bar(
        sex_counts,
        x='sex', y='num_subjects',
        color='sex',                              
        title='Sex Distribution',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig3.update_layout(xaxis_title='Sex', yaxis_title='Number of Subjects')

    row = dbc.Row([
        dbc.Col(dcc.Graph(figure=fig1), md=4),
        dbc.Col(dcc.Graph(figure=fig2), md=4),
        dbc.Col(dcc.Graph(figure=fig3), md=4),
    ], className='mt-3')
    return row

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host='0.0.0.0', port=port)
