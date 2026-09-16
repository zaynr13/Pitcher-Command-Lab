"""Native UI regression checks; run with unittest from the repository root."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class InterfaceTests(unittest.TestCase):
    def test_matchup_target_modes_plate_appearance_and_views(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(app.exception)
        app.selectbox(key='pitcher').set_value('656302').run()
        app.selectbox(key='hitter').set_value('665489').run()
        app.selectbox(key='pitch').set_value('FF').run()
        before=app.metric[2].value
        app.number_input(key='x').set_value(.7).run()
        self.assertNotEqual(before,app.metric[2].value)
        app.radio(key='mode').set_value('perfect').run()
        self.assertEqual(app.metric[2].value,app.metric[3].value)
        app.checkbox(key='fixed_seed').check().run()
        app.number_input(key='seed').set_value(5).run()
        for _ in range(30):
            next(b for b in app.button if b.label=='THROW PITCH ↗').click().run()
            self.assertFalse(app.exception)
            if app.session_state['ended']:break
        self.assertTrue(app.session_state['ended'])
        history=list(app.session_state['history'])
        app.radio[0].set_value('Methodology').run()
        self.assertFalse(app.exception)
        app.radio[0].set_value('Be the catcher').run()
        self.assertEqual(history,list(app.session_state['history']))
        self.assertEqual(app.number_input(key='x').value,.7)
        next(b for b in app.button if b.label=='New plate appearance ↗').click().run()
        self.assertFalse(app.session_state['history'])
        for key,value in [('balls',3),('strikes',2),('outs',2),('bases',7)]:
            app.selectbox(key=key).set_value(value).run()
        app.radio[0].set_value('Pro Mode').run()
        for metric in ['realistic','perfect','swing','whiff','penalty']:
            next(w for w in app.selectbox if w.label=='Map metric').set_value(metric).run()
            self.assertFalse(app.exception)
        self.assertGreater(len(app.get('plotly_chart')),2)
        second=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=30).run()
        self.assertFalse(second.session_state['history'])
        self.assertEqual(second.selectbox(key='balls').value,0)

if __name__=='__main__':unittest.main()
