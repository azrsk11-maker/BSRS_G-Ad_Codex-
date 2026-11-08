"""No-network qualification audit and GCLID review-preview. Never uploads.
Inputs are purpose-specific whitelisted extracts, not the raw contact-bearing intake sheet.
"""
from __future__ import annotations
import json, math, re, uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from qualification_sources import source_report
DUBAI=timezone(timedelta(hours=4))
HERE=Path(__file__).resolve().parent
ROLES={"off_plan","resale","tenant","seller","landlord"}
QUALIFIED_ADS_ACTION_ID="7878013428"
QUALIFIED_ADS_ACTION_NAME="qualified_lead"
INTAKE_FIELDS={"lead_id","role","accepted_at_utc","is_test"}
PURPOSE_FIELDS={"lead_id","evidence_id","decision_version","notice_version","observed_at_utc",
 "expires_at_utc","acknowledged","measurement_eligible","ad_measurement","ad_user_data","ad_personalization",
 "withdrawn_at_utc","click_id_type","click_id","attribution_captured_at_utc","record_integrity_verified"}
def when(s):
    if not isinstance(s,str): raise ValueError("INVALID_TIMESTAMP")
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("TIMESTAMP_WITHOUT_ZONE")
    return d
def parse_bool(v):
    if v is True or v is False or v is None:return v
    if v=="true":return True
    if v=="false":return False
    if v=="":return None
    raise ValueError("INVALID_BOOLEAN")
def fail(code): raise ValueError(code)
def strict_json(path):
    return strict_json_bytes(Path(path).read_bytes())
def strict_json_bytes(raw):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj: fail("DUPLICATE_JSON_KEY")
            obj[k]=v
        return obj
    def bad_constant(_): fail("NONFINITE_NUMBER")
    return json.loads(raw.decode("utf-8-sig"),object_pairs_hook=pairs,parse_constant=bad_constant)
def schema_errors(obj,schema):
    """The exact source schema subset: types/properties/required/enum/const/formats/patterns/allOf/if/then."""
    errors=[]
    types=schema.get("type"); types=[types] if isinstance(types,str) else types
    matches={"null":obj is None,"boolean":isinstance(obj,bool),"object":isinstance(obj,dict),
      "string":isinstance(obj,str),"number":isinstance(obj,(int,float)) and not isinstance(obj,bool) and math.isfinite(obj),
      "array":isinstance(obj,list)}
    if types and not any(matches.get(t,False) for t in types):return ["SCHEMA_TYPE"]
    if "const" in schema and (type(obj)!=type(schema["const"]) or obj!=schema["const"]):errors.append("SCHEMA_CONST")
    if "enum" in schema and not any(type(obj)==type(x) and obj==x for x in schema["enum"]):errors.append("SCHEMA_ENUM")
    if isinstance(obj,dict):
        errors+=["SCHEMA_REQUIRED"]*len(set(schema.get("required",[]))-set(obj))
        props=schema.get("properties",{})
        if schema.get("additionalProperties") is False and set(obj)-set(props):errors.append("SCHEMA_EXTRA_PROPERTY")
        for k,v in obj.items():
            if k in props:errors+=schema_errors(v,props[k])
    if isinstance(obj,str):
        if len(obj)<schema.get("minLength",0):errors.append("SCHEMA_MIN_LENGTH")
        if schema.get("pattern") and not re.search(schema["pattern"],obj):errors.append("SCHEMA_PATTERN")
        if schema.get("format"):
            try:
                if schema["format"]=="date-time":when(obj)
                elif schema["format"]=="uuid":uuid.UUID(obj)
            except (ValueError,TypeError):errors.append("SCHEMA_FORMAT")
    if isinstance(obj,(int,float)) and not isinstance(obj,bool) and "minimum" in schema and obj<schema["minimum"]:errors.append("SCHEMA_MINIMUM")
    for sub in schema.get("allOf",[]):
        if "if" in sub:
            if not schema_errors(obj,sub["if"]):errors+=schema_errors(obj,sub.get("then",{}))
        else:errors+=schema_errors(obj,sub)
    return errors
def safe_id(s):
    return s if isinstance(s,str) and re.fullmatch(r"[A-Za-z0-9:_-]{1,150}",s) else "INVALID_ID"
def unique_records(rows,key,allowed=None):
    out={}; conflicts=set()
    for row in rows:
        if not isinstance(row,dict):fail("INVALID_RECORD")
        if allowed and set(row)-allowed:fail("EXTRA_EXTRACT_FIELD_CONTACT_DATA_FORBIDDEN")
        if key not in row:fail("MISSING_JOIN_ID")
        k=row[key]
        if k in out and out[k]!=row:conflicts.add(k)
        else:out[k]=row
    for k in conflicts:out.pop(k,None)
    return out,conflicts
def _inspect(data,binding,purpose_rows,now,from_day=None,to_day=None,source_review=None,ledger_sha256=None):
    schema=strict_json(HERE/"schema/outcome-register-schema.json")
    if not isinstance(data,dict) or not isinstance(data.get("records"),list) or not isinstance(data.get("intake"),list):fail("INVALID_LEDGER_ENVELOPE")
    fixture=data.get("fixture_only") is True
    intake,conflicting_intake=unique_records(data["intake"],"lead_id",INTAKE_FIELDS)
    for r in intake.values():
        if not set(INTAKE_FIELDS)<=set(r) or r["role"] not in ROLES or type(r["is_test"]) is not bool:fail("INVALID_INTAKE_EXTRACT")
        when(r["accepted_at_utc"])
    purpose_by_lead=defaultdict(list)
    for p in purpose_rows:
        if not isinstance(p,dict) or set(p)-PURPOSE_FIELDS:fail("EXTRA_PURPOSE_FIELD_CONTACT_DATA_FORBIDDEN")
        if not set(PURPOSE_FIELDS)<=set(p):fail("INCOMPLETE_PURPOSE_ADAPTER")
        observed=when(p["observed_at_utc"]).astimezone(timezone.utc).isoformat()
        purpose_by_lead[p["lead_id"]].append(dict(p, observed_at_utc=observed))
    # Never guess the winner of conflicting observations at the same timestamp.
    ambiguous_purpose=set()
    for lead,items in purpose_by_lead.items():
        by_time=defaultdict(list)
        for p in items:by_time[p["observed_at_utc"]].append(p)
        if any(any(x!=ys[0] for x in ys) for ys in by_time.values()):ambiguous_purpose.add(lead)
    outcomes,conflicting_outcomes=unique_records(data["records"],"outcome_id")
    issues=[]; eligible=[]; held_people=set(); person_to_canonical=defaultdict(set); canonical_to_person=defaultdict(set)
    for original in data["records"]:
        if not isinstance(original,dict):continue
        person=original.get("person_key")
        if original.get("outcome_id") in conflicting_outcomes and person:held_people.add(person)
    for oid,r in outcomes.items():
        codes=[]
        if schema_errors(r,schema):codes.append("OUTCOME_SCHEMA_INVALID")
        lead=intake.get(r.get("lead_id")); canonical=intake.get(r.get("canonical_lead_id"))
        if not lead or not canonical or r.get("lead_id") in conflicting_intake or r.get("canonical_lead_id") in conflicting_intake:codes.append("INTAKE_JOIN_NOT_UNIQUE")
        if lead and (lead["role"]!=r.get("role")):codes.append("ROLE_JOIN_MISMATCH")
        if (lead and lead["is_test"]) or (canonical and canonical["is_test"]) or r.get("is_test") is True:codes.append("TEST_RECORD")
        if r.get("stage")!="qualified_prospect":codes.append("NOT_QUALIFIED_STAGE")
        if r.get("duplicate_of_lead_id") or r.get("qualification_status")=="DUPLICATE":codes.append("DUPLICATE_RECORD")
        if r.get("export_state") in {"RETRACTED","ADJUSTMENT_REQUIRED"} or r.get("adjusts_outcome_id"):codes.append("ADJUSTMENT_REVIEW_REQUIRED")
        try:
            occurred,recorded=when(r["occurred_at_utc"]),when(r["recorded_at_utc"])
            if occurred>now or recorded>now or recorded<occurred:codes.append("INVALID_OUTCOME_TIME_ORDER")
            if lead and occurred<when(lead["accepted_at_utc"]):codes.append("OUTCOME_BEFORE_ACCEPTANCE")
            if canonical and occurred<when(canonical["accepted_at_utc"]):codes.append("CANONICAL_ACCEPTANCE_AFTER_OUTCOME")
            if r.get("occurred_at_dubai") and when(r["occurred_at_dubai"])!=occurred:codes.append("DUBAI_TIME_MISMATCH")
        except (ValueError,KeyError,TypeError):codes.append("INVALID_OUTCOME_TIMESTAMP")
        if codes:
            issues.append({"outcome_id":safe_id(oid),"codes":sorted(set(codes))})
            if r.get("person_key") and r.get("stage")=="qualified_prospect" and "TEST_RECORD" not in codes and "DUPLICATE_RECORD" not in codes:held_people.add(r["person_key"])
            continue
        person_to_canonical[r["person_key"]].add(r["canonical_lead_id"])
        canonical_to_person[r["canonical_lead_id"]].add(r["person_key"])
        eligible.append(r)
    for person,canons in person_to_canonical.items():
        if len(canons)>1:held_people.add(person)
    for canon,people in canonical_to_person.items():
        if len(people)>1:held_people.update(people)
    eligible.sort(key=lambda r:(when(r["occurred_at_utc"]),r["outcome_id"]))
    first={}
    for r in eligible:
        if r["person_key"] in held_people:continue
        first.setdefault(r["person_key"],r)
    # UUID ordering is a stable implementation order, never evidence that one
    # distinct outcome won an indistinguishable earliest qualification time.
    earliest_ids=defaultdict(set)
    earliest_acceptance=defaultdict(dict)
    for r in eligible:
        chosen=first.get(r["person_key"])
        if chosen and when(r["occurred_at_utc"])==when(chosen["occurred_at_utc"]):
            earliest_ids[r["person_key"]].add(r["outcome_id"])
            accepted_ref={"lead_id":r["lead_id"],"role":r["role"],"accepted_at_utc":intake[r["lead_id"]]["accepted_at_utc"]}
            earliest_acceptance[r["person_key"]][(accepted_ref["lead_id"],accepted_ref["role"],accepted_ref["accepted_at_utc"])]=accepted_ref
    ambiguous_first={r["outcome_id"] for person,r in first.items() if len(earliest_ids[person])>1}
    # Filtering follows whole-history first-ever dedup; never dedup just today's slice.
    selected=[]
    for r in first.values():
        day=when(r["occurred_at_utc"]).astimezone(DUBAI).date().isoformat()
        if from_day and day<from_day:continue
        if to_day and day>to_day:continue
        selected.append((day,r))
    daily=Counter(day for day,r in selected); roles=Counter(r["role"] for day,r in selected)
    history_complete=data.get("history_complete") is True and bool(data.get("history_evidence_reference"))
    preview=[]; export_held=[]
    binding_ok=(binding.get("customer_id")=="573-038-4686" and
      str(binding.get("conversion_owner_customer_id")) in {"573-038-4686","5730384686"} and
      str(binding.get("conversion_action_id"))==QUALIFIED_ADS_ACTION_ID and
      binding.get("conversion_name")==QUALIFIED_ADS_ACTION_NAME and binding.get("mapping_verified") is True and
      binding.get("stage_key")=="qualified_lead" and binding.get("identifier_route")=="GCLID_ONLY")
    for day,r in selected:
        codes=[]
        if r["outcome_id"] in ambiguous_first:codes.append("FIRST_QUALIFICATION_TIE_REVIEW_REQUIRED")
        if not history_complete:codes.append("WHOLE_HISTORY_NOT_ATTESTED")
        if not binding_ok:codes.append("ACTION_BINDING_NOT_VERIFIED")
        if r.get("export_state")!="READY":codes.append("NOT_READY_OR_ALREADY_EXPORTED")
        if r["lead_id"] in ambiguous_purpose:codes.append("AMBIGUOUS_PURPOSE_HISTORY")
        snapshots=[p for p in purpose_by_lead.get(r["lead_id"],[]) if when(p["observed_at_utc"])<=now]
        p=max(snapshots,key=lambda x:when(x["observed_at_utc"])) if snapshots else None
        if not p:codes.append("MISSING_PURPOSE_JOIN")
        else:
            if not all(p[x] is True for x in ("acknowledged","measurement_eligible","ad_measurement","record_integrity_verified")):codes.append("PURPOSE_NOT_ESTABLISHED")
            if p["ad_user_data"]!="GRANTED" or p["ad_personalization"]!="DENIED":codes.append("PURPOSE_STATE_NOT_SUPPORTED")
            if r.get("ad_user_data")!=p["ad_user_data"] or r.get("ad_personalization")!=p["ad_personalization"]:codes.append("CONSENT_STATE_JOIN_MISMATCH")
            if not all(isinstance(p[x],str) and p[x] and p[x]!="none" for x in ("evidence_id","decision_version","notice_version")):codes.append("MISSING_PURPOSE_EVIDENCE")
            for snapshot in snapshots:
                if snapshot["evidence_id"]!=p["evidence_id"] or snapshot["withdrawn_at_utc"] is None:continue
                try:
                    withdrawal=when(snapshot["withdrawn_at_utc"])
                    codes.append("PURPOSE_WITHDRAWN" if withdrawal<=now else "INVALID_WITHDRAWAL_TIME")
                except ValueError:codes.append("INVALID_WITHDRAWAL_TIME")
            try:
                if when(p["expires_at_utc"])<=now:codes.append("PURPOSE_EXPIRED")
                captured=when(p["attribution_captured_at_utc"])
                if when(p["observed_at_utc"])>now or captured>when(r["occurred_at_utc"]):codes.append("CAPTURE_PURPOSE_TIME_MISMATCH")
            except (ValueError,TypeError):codes.append("INVALID_PURPOSE_TIMESTAMP")
            if p["click_id_type"]!="GCLID" or r.get("click_id_type")!="GCLID":codes.append("GCLID_ONLY")
            if not re.fullmatch(r"[A-Za-z0-9._~-]{1,256}",str(p["click_id"])) or p["click_id"]!=r.get("click_id"):codes.append("CLICK_ID_JOIN_MISMATCH")
            if r.get("privacy_evidence_reference")!=p["evidence_id"]:codes.append("PRIVACY_EVIDENCE_JOIN_MISMATCH")
        expected_order="BSRE:"+r["outcome_id"]
        if r.get("order_id")!=expected_order:codes.append("ORDER_ID_NOT_STABLE_CONVENTION")
        if str(r.get("conversion_action_id"))!=str(binding.get("conversion_action_id")) or r.get("conversion_name")!=binding.get("conversion_name"):codes.append("ACTION_ROW_BINDING_MISMATCH")
        if codes:export_held.append({"outcome_id":safe_id(r["outcome_id"]),"codes":sorted(set(codes))});continue
        # Internal review shape, deliberately not a provider-native upload file.
        preview.append({"outcome_id":r["outcome_id"],"google_click_id":p["click_id"],
         "conversion_action_id":str(binding["conversion_action_id"]),"conversion_name":binding["conversion_name"],
         "conversion_time":when(r["occurred_at_utc"]).astimezone(DUBAI).strftime("%Y-%m-%d %H:%M:%S+04:00"),
         "order_id":expected_order,"ad_user_data":"GRANTED","ad_personalization":"DENIED"})
    for oid in conflicting_outcomes:issues.append({"outcome_id":safe_id(oid),"codes":["CONFLICTING_OUTCOME_ID"]})
    report={"fixture_only":fixture,"evaluated_at_utc":now.isoformat(),"timezone":"Asia/Dubai",
     "history_complete_attested":history_complete,"history_truth_independently_verified":False,
     "provided_history_first_qualified_by_dubai_day":dict(sorted(daily.items())),
     "provided_history_first_qualified_by_role":dict(sorted(roles.items())),
     "qualified_target_count_in_selected_period":sum(daily.values()) if history_complete else None,
     "first_ever_claim_scope":"Only complete staff-attested supplied history; no independent person/contact dedup performed",
     "held_person_mappings":len(held_people),"outcome_issues":issues,"export_held":export_held,
     "preview_rows":len(preview),"report_contains_contact_or_click_data":False,
     "notes":["Business qualification totals do not require optional ad measurement; export has separate purpose gates",
      "No observed click-time/action-window or provider-route acceptance is certified by local capture timestamps",
      "No upload, contact outreach, live mutation or imported success is performed or inferred"]}
    report.update(source_report(selected,source_review,now,fixture,ledger_sha256,history_complete,ambiguous_first))
    bundle={"artifact_type":"GCLID_INTERNAL_REVIEW_PREVIEW_NOT_UPLOAD_FORMAT","UPLOAD_PROHIBITED":True,"fixture_only":fixture,
     "customer_id":"573-038-4686","provider_route_eligibility_verified":False,"provider_window_validation_required":True,
     "purpose_adapter_live_mapping_verified":False,"rows":preview}
    # Private minimal projection for other first-party reports. Never include
    # person keys, staff notes, contact details, permissions or click identifiers.
    selection=[{"outcome_id":r["outcome_id"],"lead_id":r["lead_id"],"role":r["role"],
      "occurred_at_utc":r["occurred_at_utc"],"accepted_at_utc":intake[r["lead_id"]]["accepted_at_utc"],
      "earliest_acceptance_references":[value for key,value in sorted(earliest_acceptance[r["person_key"]].items())],
      "first_qualification_tied":r["outcome_id"] in ambiguous_first}for day,r in selected]
    return report,bundle,selection


def inspect_reporting(data, now, from_day=None, to_day=None, source_review=None, ledger_sha256=None):
    """Reuse historical business validation without an export/write entry point."""
    report, _, selection = _inspect(data, {}, [], now, from_day, to_day, source_review, ledger_sha256)
    return report, selection
