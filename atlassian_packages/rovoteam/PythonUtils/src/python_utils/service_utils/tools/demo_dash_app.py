from dash import Dash, html, dcc, Input, Output, State, callback

app = Dash(__name__)

app.layout = html.Div(
    style={
        'fontFamily': 'Arial, sans-serif',
        'maxWidth': '800px',
        'margin': '0 auto',
        'padding': '20px'
    },
    children=[
        html.Div(
            style={
                'border': '1px solid #ddd',
                'padding': '20px',
                'borderRadius': '5px'
            },
            children=[
                html.H1('Dash Test Site'),
                html.P('This is a simple Dash application for testing purposes.'),

                html.Div(
                    style={'marginTop': '20px'},
                    children=[
                        html.H3('Test Form'),
                        dcc.Input(
                            id='name-input',
                            type='text',
                            placeholder='Enter your name',
                            style={
                                'padding': '8px',
                                'margin': '5px 0',
                                'width': '100%'
                            }
                        ),
                        html.Button(
                            'Submit',
                            id='submit-button',
                            n_clicks=0,
                            style={
                                'padding': '8px',
                                'margin': '5px 0',
                                'backgroundColor': '#4CAF50',
                                'color': 'white',
                                'border': 'none',
                                'cursor': 'pointer'
                            }
                        ),
                    ]
                ),

                html.Div(
                    id='output-div',
                    style={'marginTop': '20px'}
                )
            ]
        )
    ]
)


@callback(
    Output('output-div', 'children'),
    Input('submit-button', 'n_clicks'),
    State('name-input', 'value'),
    prevent_initial_call=True
)
def submit_form(n_clicks, name):
    if not name:
        name = 'Unknown'

    return html.Div(
        style={
            'border': '1px solid #4CAF50',
            'padding': '15px',
            'borderRadius': '5px',
            'backgroundColor': '#f0f8f0'
        },
        children=[
            html.H3('Form Submitted'),
            html.P(f'Hello, {name}! Your form was successfully submitted.'),
        ]
    )


if __name__ == '__main__':
    app.run(host='::', port=8086, debug=True, use_reloader=False)
