"""Command Lab's native Streamlit entry point."""
import secrets
import pandas as pd
import streamlit as st
from src.simulator import Simulator, Call
from src.charts import location_chart, outcomes_chart, surface_chart

st.set_page_config(page_title='Command Lab · Call the pitch',page_icon='⚾',layout='wide')
st.markdown('''<style>
.block-container{max-width:1540px;padding-top:4rem}
h1,h2,h3{letter-spacing:-.025em}h1{font-size:3rem!important}
.brand{font-size:1.25rem;font-weight:800;letter-spacing:.12em;border-bottom:1px solid #2a3646;padding-bottom:20px}
.brand span,.eyebrow{color:#ffae68}.eyebrow{font:12px monospace;letter-spacing:.14em;margin-top:24px}
[data-testid="stMetricValue"]{color:#ffae68}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#2a3646!important}
[data-testid="stMetric"]{background:#121c2a;border-radius:6px;padding:10px}
.stButton>button{border-radius:5px;min-height:44px}
</style><div class="brand">⌖ COMMAND <span>LAB</span></div>
<div class="eyebrow">THE ART OF THE PITCH CALL</div>''',unsafe_allow_html=True)
st.title('Call the pitch. Live with the miss.')
st.caption('Measured execution. Modeled outcomes. Pick your matchup, then put down a target.')

@st.cache_resource
def resources():
    return Simulator()

@st.cache_data
def methodology():
    return resources().methodology()

sim=resources()
players=sim.engine.players
names={'FF':'Four-seam','SI':'Sinker','FC':'Cutter','SL':'Slider','ST':'Sweeper','CU':'Curveball','KC':'Knuckle curve','CH':'Changeup','FS':'Splitter','SV':'Slurve','FO':'Forkball','KN':'Knuckleball'}
base_names={0:'Bases empty',1:'First',2:'Second',4:'Third',3:'First & second',5:'First & third',6:'Second & third',7:'Bases loaded'}
s=st.session_state
# Keep controls stable when a workspace hides their widgets.
for key in ('pitcher','hitter','pitch','balls','strikes','outs','bases','x','z','mode','fixed_seed','seed'):
    if key in s:s[key]=s[key]
for key,value in {'history':[],'ended':False,'last':None,'result':'','balls':0,'strikes':0,'outs':0,'bases':0,'x':0.,'z':2.5,'show_surface':False,'chart_revision':0}.items():
    if key not in s:s[key]=value

def clear_pa(reset_count=False):
    s.history=[];s.ended=False;s.last=None;s.result='';s.show_surface=False
    s.chart_revision+=1
    if reset_count:s.balls=0;s.strikes=0

def new_pa():
    clear_pa(True)

def clear_landing():
    s.last=None;s.chart_revision+=1

def select_target():
    points=s.get('target_chart',{}).get('selection',{}).get('points',[])
    if points and not s.ended:
        p=points[-1]
        s.x=round(max(-1.5,min(1.5,float(p['x']))),2)
        s.z=round(max(.75,min(4.25,float(p['y']))),2)
        s.last=None

def throw_pitch():
    try:
        c=Call(s.pitcher,s.hitter,s.pitch,s.balls,s.strikes,s.outs,s.bases,s.x,s.z,s.mode,
               int(s.seed) if s.fixed_seed else secrets.randbits(32))
        r=sim.throw(c)
        s.history.append({**r,'pitch':c.pitch,'count':f'{c.balls}–{c.strikes}'})
        s.last=r['location'];s.ended=r['state']['ended'];s.balls=r['state']['balls'];s.strikes=r['state']['strikes']
        s.result=(r['state']['result'] if s.ended else r['event']).replace('_',' ').upper()
        s.show_surface=False
        if s.fixed_seed:s.seed=(int(s.seed)+1) % (2**32)
        s.pop('error',None)
    except ValueError as exc:s.error=str(exc)

view=st.radio('Workspace',['Be the catcher','Pro Mode','Methodology'],horizontal=True,label_visibility='collapsed')
st.caption(f"{len(players['pitchers'])} pitchers · {len(players['hitters'])} hitters · Profiles frozen July 1, 2025 · Research preview")
if view!='Methodology':
    lineup,field,read=st.columns([.9,1.55,1.05],gap='large')
    with lineup:
        st.subheader('01 / The matchup')
        pitchers=sorted(players['pitchers'],key=lambda p:p['name'])
        hitters=sorted(players['hitters'],key=lambda p:p['name'])
        pids=[p['id'] for p in pitchers];hids=[h['id'] for h in hitters]
        if 'pitcher' not in s:s.pitcher=next((p['id'] for p in pitchers if 'Cease' in p['name']),pids[0])
        if 'hitter' not in s:s.hitter=next((h['id'] for h in hitters if 'Guerrero' in h['name']),hids[0])
        st.selectbox('Pitcher',pids,format_func=lambda pid:sim.engine.pitchers[pid]['name'],key='pitcher',on_change=new_pa)
        p=sim.engine.pitchers[s.pitcher]
        st.caption(f"{p['hand']}HP · {p['n']:,} training pitches · {p['outings']} outings")
        st.selectbox('Hitter',hids,format_func=lambda hid:sim.engine.hitters[hid]['name'],key='hitter',on_change=new_pa)
        h=sim.engine.hitters[s.hitter]
        st.caption(f"{'Switch' if h['switch'] else h['hand']+'-handed'} · {h['n']:,} pitches seen · {h['pa']:,} PA")
        st.divider()
        st.markdown('**Game situation**')
        a,b,c=st.columns(3)
        a.selectbox('Balls',range(4),key='balls',on_change=clear_pa)
        b.selectbox('Strikes',range(3),key='strikes',on_change=clear_pa)
        c.selectbox('Outs',range(3),key='outs',on_change=clear_pa)
        st.selectbox('Runners',list(base_names),format_func=base_names.get,key='bases',on_change=clear_pa)
        st.button('New plate appearance ↗',on_click=new_pa,width="stretch")
        with st.expander('Simulation seed'):
            st.checkbox('Use reproducible seed',key='fixed_seed')
            st.number_input('Seed',0,2**32-1,1729,key='seed',help='With reproducible mode enabled, the seed advances by one after each pitch.')
    with field:
        st.subheader(f'02 / Pick your spot · {s.balls}–{s.strikes}')
        st.radio('Execution',['realistic','perfect'],format_func=lambda v:v.title()+' execution',horizontal=True,key='mode')
        pitches={v['type']:v for v in p['pitches']}
        if s.get('pitch') not in pitches:s.pitch=max(p['pitches'],key=lambda v:v['usage'])['type']
        st.selectbox('Pitch type',list(pitches),format_func=lambda v:f"{names.get(v,v)} · {pitches[v]['mean_velocity']:.1f} mph · {pitches[v]['usage']:.1%}",key='pitch',on_change=clear_landing)
        a,b=st.columns(2)
        a.number_input('Horizontal target (ft)',-1.5,1.5,step=.05,key='x',on_change=clear_landing)
        b.number_input('Target height (ft)',.75,4.25,step=.05,key='z',on_change=clear_landing)
        call=Call(s.pitcher,s.hitter,s.pitch,s.balls,s.strikes,s.outs,s.bases,s.x,s.z,s.mode)
        analysis=sim.analyze(call);a=analysis[s.mode];command=pitches[s.pitch]['command']
        st.plotly_chart(location_chart([s.x,s.z],command,h,a,s.mode,s.last),key='target_chart',
                        on_select=select_target,selection_mode='points',use_container_width=True,theme=None,
                        config={'displayModeBar':False})
        st.caption('Catcher’s view · Click the chart to aim on a 0.05-ft grid, or use the precise controls above. Ellipses show 50% / 80% fitted landing regions.')
        st.button('THROW PITCH ↗',type='primary',on_click=throw_pitch,disabled=s.ended,width="stretch")
        if s.result:st.success(s.result+(' · Plate appearance complete' if s.ended else ' · Choose your next call'))
        if 'error' in s:st.warning(s.error)
    with read:
        st.subheader('03 / The read')
        st.caption('Expected response across possible locations. Lower run value favors the pitcher.')
        st.metric('Swing',f"{a['swing']:.1%}")
        st.metric('Whiff · if swinging',f"{a['whiff_given_swing']:.1%}")
        st.metric('Offensive run value',f"{a['run_value']:+.3f}")
        left,right=st.columns(2)
        left.metric('Perfect',f"{analysis['perfect']['run_value']:+.3f}")
        right.metric('Realistic',f"{analysis['realistic']['run_value']:+.3f}")
        st.metric('Command penalty',f"{analysis['command_penalty']:+.3f}")
        st.caption('Positive penalty means execution uncertainty adds modeled offensive value.')
        with st.expander('Under the model'):
            support=a['target_support'];cal=analysis['command_validation']
            st.write(f"{support['n']:,} training targets within 0.5 ft of the nearest grid target.")
            if not support['supported']:st.warning('Limited target support: extrapolation; optimizer excludes this grid region.')
            if cal:st.write(f"Pitcher held-out 80% coverage: {cal['coverage80']:.1%} across {cal['n']:,} pitches.")
            st.write(f"{command['n']:,} command observations. Sample size is not a calibrated confidence guarantee.")
            st.write(f"Mean miss: {command['mean'][0]:.1f}″ horizontal / {command['mean'][1]:.1f}″ vertical.")
            st.write(f"Standard deviation: {command['covariance'][0][0]**.5:.1f}″ / {command['covariance'][1][1]**.5:.1f}″.")
            st.write(f"Conditional on in-play contact: {a['exit_velocity_given_in_play']:.1f} mph exit velocity · {a['xwoba_given_in_play']:.3f} xwOBA.")
            st.write(f"Integration SE: {a['integration_se']:.4f} runs. Numerical uncertainty only; model and target-measurement uncertainty are not quantified.")
        if st.button('Find best modeled call ↗',width="stretch"):s.show_surface=True
        if s.show_surface or view=='Pro Mode':
            surface=sim.surface(call);best=surface['best_'+s.mode]
            if best:st.info(f"Best grid call: {names.get(best['pitch'],best['pitch'])} at ({best['target'][0]:.2f}, {best['target'][1]:.2f}) ft · {best[s.mode]:+.3f} runs.")
            else:st.warning('Insufficient target support for optimization in this matchup.')
    with st.expander('All expected pitch outcomes'):
        st.plotly_chart(outcomes_chart(a['probabilities']),use_container_width=True,theme=None)
    if view=='Pro Mode':
        st.divider();st.subheader('Pro Mode / Target lab')
        st.caption('Execution changes the decision. Compare every eligible pitch on one shared scale.')
        metrics={'realistic':'Realistic run value','perfect':'Perfect run value','swing':'Swing probability','whiff':'Whiff, given swing','penalty':'Command penalty'}
        metric=st.selectbox('Map metric',list(metrics),format_func=metrics.get)
        rows=surface['cells'];values=[r['realistic']-r['perfect'] if metric=='penalty' else r[metric] for r in rows]
        cols=st.columns(min(3,len(pitches)))
        for i,pt in enumerate(pitches):
            with cols[i%len(cols)]:
                st.markdown('**'+names.get(pt,pt)+'**')
                st.plotly_chart(surface_chart([r for r in rows if r['pitch']==pt],metric,(min(values),max(values))),use_container_width=True,theme=None,key='surface_'+pt)
        st.caption('Faded cells have fewer than 20 nearby training targets. Search: 99 targets per pitch, 64 common draws. Grid optimum, not a continuous optimum or a validated coaching recommendation.')
    st.divider();st.subheader('Plate appearance / Pitch log')
    if s.history:
        log=s.history
        if s.ended:
            best_i=min(range(len(log)),key=lambda i:log[i]['decision_loss']);worst_i=max(range(len(log)),key=lambda i:log[i]['decision_loss'])
            st.info(f"Decision percentile: {sum(r['decision_percentile'] for r in log)/len(log):.0f} / 100 · {sum(r['decision_loss'] for r in log):.3f} cumulative modeled runs lost vs grid. Best call: pitch {best_i+1}; largest loss: pitch {worst_i+1}. This ranks decisions, not outcome luck.")
        st.dataframe(pd.DataFrame([{'#':i+1,'Pitch':names.get(r['pitch'],r['pitch']),'Count':r['count'],
            'Target (ft)':', '.join(f'{v:.2f}' for v in r['target']),'Result':r['event'].replace('_',' '),
            'Expected RV':r['expected']['run_value'],'Decision loss':r['decision_loss'],'Seed':r['seed'],
            'Grid alternative':f"{names.get(r['optimal']['pitch'],r['optimal']['pitch'])} · "+', '.join(f'{v:.2f}' for v in r['optimal']['target'])} for i,r in enumerate(log)]),hide_index=True,width="stretch")
    else:st.caption('Your pitch-by-pitch decisions will appear here.')
else:
    st.subheader('What the model knows. What it doesn’t.')
    st.write('Historical predictions do not establish that changing a target causes a better result.')
    cols=st.columns(2)
    with cols[0]:
        st.markdown('### 01 / Estimated execution')
        st.write('Pitcher/pitch-type Gaussian errors are partially pooled toward pitch-type and league priors. Targets use estimated pre-pitch glove positions. Published in-sample inferred targets are excluded.')
        st.markdown('### 02 / Hitter response')
        st.write('Regularized probability models estimate swing, called strike and contact. Location interactions let hitters and pitch types differ. Models with and without player effects compete on July validation.')
    with cols[1]:
        st.markdown('### 03 / Honest evaluation')
        st.write('Training ends June 30, 2025; July selects models; August onward is held out. Run value uses a cross-fitted linear feature and boosted trees. It is not a causal estimate or xwOBA.')
        st.markdown('### 04 / Limits that matter')
        st.write('Glove position is not verified intent. Camera reconstruction introduces correlated error. Bunting, hit-by-pitch, automatic balls, sequencing, injuries and changing arsenals are not simulated. Play ends at the plate appearance.')
    d=methodology();c=d['command'];t=c['test']['pitcher_pitch_type']
    st.subheader('Observed data & held-out results')
    st.write(f"{c['usable_regular_season']:,} usable command pitches · {t['n']:,} held-out observations · 80% region coverage: {t['coverage_80']:.1%} · horizontal / vertical RMSE: {t['rmse_x_inches']:.2f}″ / {t['rmse_z_inches']:.2f}″.")
    rows=[]
    for k,r in d['response']['models'].items():
        if k=='run_value':
            v=d['value'];rows.append({'Model':'Run value','Selected':v['selected'],'Test loss / RMSE':v['models'][v['selected']]['test_rmse'],'Baseline':v['models']['tree']['test_rmse']})
        else:
            m=r[r['selected']]['test'];b=r['agnostic']['test']
            rows.append({'Model':k.replace('_',' ').title(),'Selected':r['selected'],'Test loss / RMSE':m.get('log_loss',m.get('rmse')),'Baseline':b.get('log_loss',b.get('rmse'))})
    st.dataframe(rows,hide_index=True,width="stretch")
    st.caption('Lower is better. Baseline: player-agnostic heads; tree for run value. Separate heads are not guaranteed to be mutually calibrated. Aggregate validation does not prove subgroup reliability or policy improvement.')
    e=d['external'];v=e['models']['run_value']
    st.subheader('External evaluation · '+' to '.join(e['dates']))
    st.write(f"{e['n']:,} pitches across {e['games']} unused games. Run-value RMSE: {v['rmse']:.4f} versus {v['linear_baseline_rmse']:.4f} for the linear baseline. Swing log loss: {e['models']['swing']['log_loss']:.4f}.")
    st.caption('2026 locations converted to the 2025 reference plane. This 12-day conditional-response check is not full-season or end-to-end policy validation. ABS and behavioral drift remain.')
    with st.expander('Detailed validation reports'):
        st.json(d)
    st.markdown('Sources: [OpenCommand / Tom Kim](https://github.com/tomdoyo/open-command) · [MLB Statcast](https://baseballsavant.mlb.com/csv-docs). OpenCommand-derived profiles: CC BY-NC-SA 4.0. Noncommercial research preview; not affiliated with MLB.')
st.caption('COMMAND LAB · Measured execution. Modeled outcomes. No guarantees.')
