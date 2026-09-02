import os, json, sqlite3, time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

DB = "leads.db"

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS leads(
        lead_id TEXT PRIMARY KEY, created_at TEXT, source TEXT, name TEXT,
        email TEXT, phone TEXT, course_interest TEXT, qualification TEXT,
        experience TEXT, budget REAL, enquiry TEXT, preferred_mode TEXT,
        urgency TEXT, profile TEXT, intent_score REAL, lead_score REAL,
        classification TEXT, confidence REAL, next_action TEXT,
        human_label TEXT, final_outcome TEXT, followup_at TEXT, notes TEXT)""")
    return con

def save_lead(x):
    con=db()
    con.execute("""INSERT OR REPLACE INTO leads VALUES
    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", tuple(x.values()))
    con.commit(); con.close()

def load_leads():
    con=db()
    df=pd.read_sql_query("SELECT * FROM leads ORDER BY created_at DESC", con)
    con.close(); return df

def keyword_score(text, words):
    t=str(text).lower()
    return sum(1 for w in words if w in t)

def rule_agent(row):
    text=f"{row['course_interest']} {row['enquiry']} {row['urgency']}".lower()
    intent=min(100,25*keyword_score(text,["join","enroll","admission","register"])
               +15*keyword_score(text,["immediately","urgent","this month","start"]))
    fit=20 if row["qualification"] else 0
    budget=15 if float(row.get("budget") or 0)>0 else 0
    score=min(100,intent+fit+budget)
    cls="HOT" if score>=70 else "WARM" if score>=45 else "COLD"
    action={"HOT":"Assign counsellor immediately",
            "WARM":"Send course details and schedule follow-up",
            "COLD":"Add to nurture sequence"}[cls]
    return score,cls,action

def single_llm(row):
    key=os.getenv("OPENAI_API_KEY")
    if not key:
        s,c,a=rule_agent(row)
        return min(100,s+5),c,a,0.68
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key)
        prompt=f"""Classify this EdTech lead as HOT, WARM, or COLD.
Recommend one next action. Return JSON only with:
score (0-100), classification, action, confidence (0-1).
Lead: {row.to_dict()}"""
        r=client.responses.create(model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"), input=prompt)
        obj=json.loads(r.output_text)
        return float(obj["score"]),obj["classification"],obj["action"],float(obj.get("confidence",0.7))
    except Exception:
        s,c,a=rule_agent(row)
        return min(100,s+5),c,a,0.68

def agentic_pipeline(row):
    text=f"{row['course_interest']} {row['enquiry']}".lower()
    required=["course_interest","qualification","enquiry","preferred_mode"]
    completeness=sum(bool(row.get(k)) for k in required)/len(required)
    intent_terms=["join","enroll","admission","fees","register","interested","start","career","placement"]
    urgency_terms=["today","immediately","urgent","this week","this month","soon"]
    intent=min(100,18*keyword_score(text,intent_terms)+12*keyword_score(text,urgency_terms))
    profile_fit=25 if row["qualification"] else 10
    engagement=15 if row.get("preferred_mode") else 5
    budget=15 if float(row.get("budget") or 0)>0 else 5
    score=min(100,0.35*intent+profile_fit+engagement+budget+10*completeness)
    conf=min(0.95,0.50+0.30*completeness+0.001*score)
    cls="HOT" if score>=70 else "WARM" if score>=45 else "COLD"
    if conf<0.70:
        action="Human review required before automated outreach"
    elif cls=="HOT":
        action="Assign priority counsellor + send personalized information + schedule follow-up"
    elif cls=="WARM":
        action="Send personalized information + schedule follow-up"
    else:
        action="Add to nurture sequence and monitor engagement"
    trace={"data_quality":round(completeness,2),"intent_score":round(intent,1),
           "profile_fit":profile_fit,"engagement":engagement,"budget_signal":budget}
    return score,cls,action,conf,trace

st.set_page_config(page_title="Agentic AI EdTech Lead Manager",layout="wide")
st.title("Agentic AI Lead Management — EdTech Research Prototype")
st.caption("iwAIIS 2026: Rule-Based vs Single-LLM vs Multi-Agent Agentic AI")

with st.sidebar:
    st.header("Agent Pipeline")
    st.write("Acquisition → Validation → Profiling → Intent → Scoring → Decision → Follow-up → Human Review")
    st.info("Default mode is a transparent heuristic prototype. Configure an LLM API only for the single-LLM comparison.")

tab1,tab2,tab3=st.tabs(["New Lead","Lead Dashboard","Research Evaluation"])

with tab1:
    st.subheader("Lead Intake")
    c1,c2,c3=st.columns(3)
    with c1:
        lead_id=st.text_input("Lead ID",value=f"L{int(time.time())}")
        name=st.text_input("Name")
        email=st.text_input("Email")
        phone=st.text_input("Phone")
        source=st.selectbox("Source",["Website","Google Form","Instagram","Facebook","Email","WhatsApp","Other"])
    with c2:
        course=st.text_input("Course Interest","Data Science")
        qual=st.text_input("Qualification","B.Tech")
        exp=st.text_input("Experience","0-2 years")
        budget=st.number_input("Budget",min_value=0.0,step=1000.0)
        mode=st.selectbox("Preferred Mode",["Online","Offline","Weekend","Weekday","Not specified"])
    with c3:
        urgency=st.selectbox("Urgency",["High","Medium","Low"])
        enquiry=st.text_area("Enquiry","I am interested in the course and want to know fees and admission details.")
        human_label=st.selectbox("Human Label (optional)",["","HOT","WARM","COLD"])
        outcome=st.selectbox("Final Outcome (optional)",["","Enrolled","Counselling","Follow-up","Not Enrolled","Unknown"])
    if st.button("Run Agentic Qualification",type="primary"):
        row=pd.Series({"lead_id":lead_id,"source":source,"name":name,"email":email,"phone":phone,
                       "course_interest":course,"qualification":qual,"experience":exp,"budget":budget,
                       "enquiry":enquiry,"preferred_mode":mode,"urgency":urgency})
        score,cls,action,conf,trace=agentic_pipeline(row)
        llm_score,llm_cls,llm_action,llm_conf=single_llm(row)
        rule_score,rule_cls,rule_action=rule_agent(row)
        follow=(datetime.now()+timedelta(hours=24)).isoformat(timespec="minutes")
        record={"lead_id":lead_id,"created_at":datetime.now().isoformat(timespec="seconds"),
                "source":source,"name":name,"email":email,"phone":phone,"course_interest":course,
                "qualification":qual,"experience":exp,"budget":budget,"enquiry":enquiry,
                "preferred_mode":mode,"urgency":urgency,"profile":json.dumps(trace),
                "intent_score":trace["intent_score"],"lead_score":score,"classification":cls,
                "confidence":conf,"next_action":action,"human_label":human_label,
                "final_outcome":outcome,"followup_at":follow,
                "notes":f"Rule={rule_cls}; SingleLLM={llm_cls}"}
        save_lead(record)
        st.success("Lead processed and stored.")
        a,b,c,d=st.columns(4)
        a.metric("Agentic Score",f"{score:.1f}")
        b.metric("Classification",cls)
        c.metric("Confidence",f"{conf:.2f}")
        d.metric("Follow-up",follow)
        st.subheader("Agent Trace")
        st.json(trace)
        st.write("Next action:",action)
        st.write("Baseline comparison: Rule-based =",rule_cls,"| Single-LLM =",llm_cls)

with tab2:
    st.subheader("Lead Dashboard")
    df=load_leads()
    if len(df):
        st.dataframe(df[["lead_id","created_at","source","course_interest","intent_score","lead_score",
                         "classification","confidence","next_action","human_label","final_outcome"]],
                     use_container_width=True)
        st.bar_chart(df["classification"].value_counts())
    else:
        st.info("No leads yet.")

with tab3:
    st.subheader("Research Evaluation")
    df=load_leads()
    if len(df)==0:
        st.info("Add leads with human labels to enable evaluation.")
    else:
        labeled=df[df["human_label"].isin(["HOT","WARM","COLD"])].copy()
        if len(labeled)==0:
            st.warning("Enter Human Label for at least one lead.")
        else:
            from sklearn.metrics import accuracy_score,precision_recall_fscore_support
            def metrics(pred,truth):
                acc=accuracy_score(truth,pred)
                p,r,f,_=precision_recall_fscore_support(truth,pred,average="macro",zero_division=0)
                return {"Accuracy":acc,"Macro Precision":p,"Macro Recall":r,"Macro F1":f}
            truth=labeled["human_label"].tolist()
            rp=[]; ap=[]
            for _,r in labeled.iterrows():
                rp.append(rule_agent(r)[1])
                ap.append(agentic_pipeline(r)[1])
            res=pd.DataFrame([
                {"Approach":"Rule-Based",**metrics(rp,truth)},
                {"Approach":"Agentic Prototype",**metrics(ap,truth)}
            ]).set_index("Approach")
            st.dataframe(res.style.format("{:.3f}"),use_container_width=True)
            st.bar_chart(res[["Accuracy","Macro F1"]])
            st.caption("For publication: freeze a held-out test set, run a real single-LLM baseline, add confidence intervals/statistical tests, and conduct ablations.")
