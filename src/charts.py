"""Presentation-only charts; predictions are supplied by the inference engine."""
import numpy as np
import plotly.graph_objects as go

ORANGE = '#ffae68'
BLUE = '#70a9cf'

def style(fig, height=420):
    fig.update_layout(template='plotly_dark', paper_bgcolor='#121c2a', plot_bgcolor='#121c2a',
                      font=dict(color='#c8d2dd'), height=height, margin=dict(l=35,r=20,t=25,b=40),
                      legend=dict(orientation='h',y=-.15), dragmode=False)
    fig.update_xaxes(gridcolor='#223143', zeroline=False)
    fig.update_yaxes(gridcolor='#223143', zeroline=False)
    return fig

def strike_zone(fig, bottom=1.5, top=3.5):
    fig.add_shape(type='rect',x0=-.7083,x1=.7083,y0=bottom,y1=top,line=dict(color='#c8d2dd',width=1.5))
    for i in (1,2):
        fig.add_shape(type='line',x0=-.7083+1.4166*i/3,x1=-.7083+1.4166*i/3,y0=bottom,y1=top,line=dict(color='#657487',width=.5))
        fig.add_shape(type='line',x0=-.7083,x1=.7083,y0=bottom+(top-bottom)*i/3,y1=bottom+(top-bottom)*i/3,line=dict(color='#657487',width=.5))

def location_chart(target, profile, hitter, analysis, mode, last=None):
    fig=go.Figure()
    # A selectable 0.05-ft grid gives native chart targeting without a JS server.
    x,z=np.meshgrid(np.linspace(-1.5,1.5,61),np.linspace(.75,4.25,71))
    fig.add_trace(go.Scatter(x=x.ravel(),y=z.ravel(),mode='markers',name='Aim',
        marker=dict(size=8,color='rgba(112,169,207,0.015)'),showlegend=False,
        hovertemplate='Aim: %{x:.2f}, %{y:.2f} ft<extra></extra>'))
    loc=np.array(analysis['locations'])
    fig.add_trace(go.Scatter(x=loc[:,0],y=loc[:,1],mode='markers',name='Possible locations',
        marker=dict(color=BLUE,size=4,opacity=.4),hoverinfo='skip'))
    if mode=='realistic':
        values,vectors=np.linalg.eigh(np.array(profile['covariance']))
        theta=np.linspace(0,2*np.pi,120)
        for cover,dash in ((.8,'dash'),(.5,'solid')):
            ellipse=(vectors @ (np.sqrt(values[:,None]*(-2*np.log(1-cover)))*np.array([np.cos(theta),np.sin(theta)])))/12
            ellipse+=np.array(target)[:,None]+np.array(profile['mean'])[:,None]/12
            fig.add_trace(go.Scatter(x=ellipse[0],y=ellipse[1],mode='lines',name=f'{cover:.0%} region',
                line=dict(color=BLUE,width=1,dash=dash),hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=[target[0]],y=[target[1]],mode='markers',name='Target',
        marker=dict(symbol='cross',size=17,color=ORANGE),hoverinfo='skip'))
    if last is not None:
        fig.add_trace(go.Scatter(x=[last[0]],y=[last[1]],mode='markers',name='Realized pitch',
            marker=dict(size=10,color='white'),hovertemplate='%{x:.2f}, %{y:.2f} ft<extra></extra>'))
    strike_zone(fig,hitter.get('zone_bottom') or 1.5,hitter.get('zone_top') or 3.5)
    style(fig,480)
    fig.update_layout(clickmode='event+select',uirevision='zone')
    fig.update_xaxes(range=[-1.9,1.9],title='Horizontal location · feet',fixedrange=True)
    fig.update_yaxes(range=[.25,4.8],title='Height · feet',scaleanchor='x',scaleratio=1,fixedrange=True)
    return fig

def outcomes_chart(probabilities):
    pairs=sorted(probabilities.items(),key=lambda item:item[1])
    fig=go.Figure(go.Bar(x=[v for _,v in pairs],y=[k.replace('_',' ').title() for k,_ in pairs],
        orientation='h',marker_color=BLUE,hovertemplate='%{y}: %{x:.1%}<extra></extra>'))
    style(fig,330);fig.update_xaxes(tickformat='.0%',title='Probability per pitch')
    return fig

def surface_chart(cells, metric, limits):
    values=[c['realistic']-c['perfect'] if metric=='penalty' else c[metric] for c in cells]
    fig=go.Figure(go.Scatter(x=[c['target'][0] for c in cells],y=[c['target'][1] for c in cells],mode='markers',
        marker=dict(symbol='square',size=23,color=values,cmin=limits[0],cmax=limits[1],
            colorscale=[[0,'#27506e'],[1,'#e6a15f']],showscale=True,
            opacity=[1 if c['target_support']['supported'] else .2 for c in cells]),
        customdata=[[v,c['target_support']['n']] for v,c in zip(values,cells)],
        hovertemplate='(%{x:.2f}, %{y:.2f}) ft<br>Value: %{customdata[0]:.4f}<br>Nearby targets: %{customdata[1]}<extra></extra>'))
    strike_zone(fig);style(fig,390)
    fig.update_xaxes(range=[-1.8,1.8],title='Horizontal · feet',fixedrange=True)
    fig.update_yaxes(range=[.4,4.6],title='Height · feet',fixedrange=True)
    return fig
