"""Four campaign-entry candidates for review; no CMS, Ads or registry writer."""
from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path

from compile_native_manifest import compile_manifest

ROOT=Path(__file__).resolve().parents[2]
OUTPUT='tools/native-wordpress/entry-drafts/four-campaign-proposal.json'
INPUTS={
 'registry':'docs/google-ads/planned_campaign_page_registry.json',
 'allocation':'docs/google-ads/page_family_allocation.json',
 'native_manifest':'tools/native-wordpress/native-page-manifest.json',
 'release_controls':'config/release_controls.json',
 'historical_ads':'docs/audit/ACCOUNT_AD_URL_READBACK_2026-11-07.json',
 'family_decisions':'tools/native-wordpress/entry-drafts/primary-family-decisions.json',
 'public_identities':'docs/audit/NATIVE_ENTRY_CANDIDATES_2026-11-13.json'}
SETTINGS=(
 ('BUYERS','BSRE-C0121','OFP',('RDY',),('/enquire/off-plan/','/enquire/resale/'),'buyers.html',None),
 ('OWNERS','BSRE-C0336','SEL',('LND',),('/enquire/sell/','/enquire/let/'),'owners.html',None),
 ('TENANTS','BSRE-C0301','RNT',(),('/enquire/rent/',),None,'/enquire/rent/'),
 ('BRAND','BSRE-C0281','CMP',(),('/enquire/off-plan/','/enquire/resale/','/enquire/rent/','/enquire/sell/','/enquire/let/'),None,'/enquire/'))
EXPECTED_BUDGETS={'BUYERS':1200,'OWNERS':400,'TENANTS':300,'BRAND':100}
# Dated account readback and the existing four-campaign allowlist, never new IDs.
EXPECTED_IDS={'BUYERS':'24372566774','OWNERS':'24367388382','TENANTS':'24378494092','BRAND':'24378494098'}
MAX_BYTES=1024*1024


def need(value,code):
    if not value:raise ValueError(code)


def same(left,right):
    if type(left)is not type(right):return False
    if isinstance(right,dict):return left.keys()==right.keys()and all(same(left[k],v)for k,v in right.items())
    if isinstance(right,list):return len(left)==len(right)and all(same(a,b)for a,b in zip(left,right))
    return left==right


def load_inputs(root=ROOT):
    loaded={};pins={}
    for name,relative in INPUTS.items():
        path=root/relative
        need(path.is_file()and not path.is_symlink(),'INPUT_NOT_REGULAR')
        with path.open('rb')as stream:blob=stream.read(MAX_BYTES+1)
        need(0<len(blob)<=MAX_BYTES,'INPUT_BYTE_BOUND')
        loaded[name]=json.loads(blob.decode('utf-8-sig'));pins[relative]=hashlib.sha256(blob).hexdigest()
    for name in ('buyers.html','owners.html'):
        relative='tools/native-wordpress/entry-drafts/'+name
        with(root/relative).open('rb')as stream:blob=stream.read(16385)
        need(0<len(blob)<16384,'DRAFT_BYTE_BOUND')
        pins[relative]=hashlib.sha256(blob).hexdigest()
    return loaded,pins


def compile_proposal(inputs,pins):
    native=compile_manifest(inputs['registry'],inputs['allocation'])
    need(same(native,inputs['native_manifest']),'NATIVE_MANIFEST_DRIFT')
    release=inputs['release_controls']
    need(release['account_id']=='573-038-4686'and release['currency']=='AED'and
         type(release['aggregate_average_daily_budget'])is int and release['aggregate_average_daily_budget']==2000 and
         release['release_authorized']is False and release['ads_activation_authorized']is False,'RELEASE_CONTEXT_CHANGED')
    campaign_config={r['name']:r for r in release['campaigns']}
    need(len(campaign_config)==len(release['campaigns'])==4,'EXACT_FOUR_CAMPAIGNS_REQUIRED')
    historical=inputs['historical_ads']
    need(historical['account_id']=='573-038-4686'and historical['production_authorized']is False and
         historical['observed_date_utc']=='2026-11-07','HISTORICAL_IDENTITY_CONTEXT_CHANGED')
    observed=defaultdict(set)
    historical_urls=defaultdict(set)
    for row in historical['ads_in_export_order']:
        observed[row['Campaign']].add(row['Campaign ID']);historical_urls[row['Campaign']].add(row['Final URL'])
    decisions=inputs['family_decisions']
    need(decisions['scope']=='OWNER_APPROVED_DRAFT_CLASSIFICATION_ONLY'and
         decisions['controls']['planning_registry_modified']is False and
         decisions['controls']['publication_authorized']is False and
         decisions['controls']['tenants_or_brand_reclassified']is False,'FAMILY_DECISION_SCOPE_CHANGED')
    family_decisions={r['campaign_name']:r for r in decisions['decisions']}
    origin=native['site_origin_expected'];identity=inputs['public_identities']
    need(identity['scope']=='PUBLIC_WORDPRESS_IDENTITIES_NOT_CAMPAIGN_BINDING_OR_RELEASE'and
         identity['http_status']==200 and identity['redirect_followed']is False and
         same(identity['controls'],{'public_native_identities_verified':True,'internal_campaign_ownership_verified':False,
              'path_availability_for_new_pages_verified':False,'consent_or_conversion_acceptance_verified':False,
              'enquiries_submitted':0,'production_writes':0,'ads_changes':0,'release_authorized':False}),
         'PUBLIC_READBACK_IS_NOT_RELEASE_AUTHORITY')
    public=identity['pages']
    need(len(public)==6 and len({r['id']for r in public})==6 and len({r['link']for r in public})==6,'PUBLIC_PAGE_IDENTITY_COLLISION')
    pages={r['link']:r for r in public}
    hub=pages.get(origin+'/enquire/')
    need(hub is not None and hub['parent']==0,'PUBLIC_HUB_PARENT_CHANGED')
    for row in public:
        need(type(row['id'])is int and row['id']>0 and row['type']=='page'and row['status']=='publish','PUBLIC_NATIVE_PAGE_NOT_PUBLISHED')
        need(row is hub or row['parent']==hub['id'],'PUBLIC_SERVICE_PARENT_CHANGED')
    slots={r['campaign_key']:r for r in native['pages']};output=[]
    for role,key,family,secondary,paths,fragment,reuse in SETTINGS:
        name='BSRE_V2_SEARCH_'+role+'_UAE_EN';config=campaign_config.get(name)
        need(config is not None and type(config['average_daily_budget'])is int and
             config['average_daily_budget']==EXPECTED_BUDGETS[role]and
             config['status']=='PAUSED_CONSTRUCTION'and config['google_campaign_id']is None,
             'CAMPAIGN_PLAN_NOT_HELD_OR_BUDGET_CHANGED')
        need(observed[name]=={EXPECTED_IDS[role]},'HISTORICAL_CAMPAIGN_ID_NOT_ALLOWLISTED')
        slot=slots.get(key);need(slot is not None and slot['family_code']==family,'CANDIDATE_SLOT_FAMILY_CHANGED')
        need(all(origin+path in pages for path in paths),'SERVICE_ROUTE_NOT_IN_PUBLIC_READBACK')
        if role in ('BUYERS','OWNERS'):
            choice=family_decisions.get(name)
            need(choice is not None and choice['primary_family_code']==family and
                 same(choice['secondary_family_codes_preserved'],list(secondary))and
                 choice['historically_observed_google_campaign_id']in observed[name]and
                 same(choice['existing_enquiry_links_preserved'],list(paths)), 'OWNER_PRIMARY_OR_SECONDARY_DECISION_CHANGED')
            need(all(choice[k]is None for k in ('planning_slot_campaign_key','planning_slot_page_id','designated_entry_url','cms_page_id')),
                 'PRIMARY_FAMILY_RECORD_IS_NOT_A_DEPLOYMENT_BINDING')
            need(historical_urls[name]=={origin+path for path in paths},'HISTORICAL_SERVICE_DESTINATIONS_CHANGED')
        else:
            need(historical_urls[name]=={origin+reuse},'REUSE_DOES_NOT_MATCH_HISTORICAL_ENTRY')
        candidate=pages[origin+reuse]if reuse else None
        blockers=['FACTUAL_SERVICE_AND_RIGHTS_SIGNOFF','INDIVIDUAL_SLOT_AND_HISTORICAL_BRIEF_REVIEW',
                  'INTERNAL_NATIVE_OWNERSHIP_AND_ROUTE_RECONCILIATION','CONSENT_ATTRIBUTION_RECEIPT_AND_ACCESSIBILITY_ACCEPTANCE',
                  'UNLISTED_SEARCH_SITEMAP_MENU_FEED_AND_ADS_CRAWLER_ACCEPTANCE','BOTH_FULL_KEYWORD_LIBRARIES_AND_FRESH_EFFECTIVE_EXCLUSIONS',
                  'STAFF_CAPACITY_RECOVERY_IMPORT_AND_INDEPENDENT_REVIEW','SEPARATE_ACTION_SPECIFIC_RELEASE_AUTHORIZATION']
        if role=='BRAND':blockers.append('CMP_BRAND_ROLE_AND_COMPETING_BRIEF_REVIEW')
        output.append({'campaign_name':name,'historically_observed_google_campaign_id':next(iter(observed[name])),
            'campaign_id_observed_on':historical['observed_date_utc'],'latest_campaign_configuration_verified':False,
            'average_daily_budget_aed_proposed':config['average_daily_budget'],'budget_type':'AGGREGATE_AVERAGE_NOT_HARD_CAP',
            'candidate_planning_campaign_key':key,'candidate_landing_page_id':slot['landing_page_id'],
            'primary_family_candidate':family,'secondary_service_families_preserved':list(secondary),
            'source_registry_proposed_path':slot['proposed_path'],
            'candidate_entry_path':reuse or slot['proposed_path'],
            'candidate_kind':'EXISTING_NATIVE_PAGE_REUSE_REVIEW'if reuse else 'NEW_NATIVE_ENTRY_REVIEW',
            'publicly_observed_candidate_url':candidate['link']if candidate else None,
            'publicly_observed_candidate_cms_id':candidate['id']if candidate else None,
            'public_identity_observed_at':identity['observed_at_utc']if candidate else None,
            'source_path_differs_from_reuse_candidate':bool(reuse and reuse!=slot['proposed_path']),
            'draft_fragment':'tools/native-wordpress/entry-drafts/'+fragment if fragment else None,
            'existing_service_paths_preserved':list(paths),'tenant_form_is_direct_entry':role=='TENANTS',
            'create_self_link_cta':False,'actual_planning_slot_binding_approved':False,
            'actual_cms_ownership_binding_approved':False,'campaign_url_change_approved':False,
            'remaining_blockers':blockers})
    need(sum(r['average_daily_budget_aed_proposed']for r in output)==2000,'BUDGET_SUM_CHANGED')
    need(len({r['candidate_planning_campaign_key']for r in output})==len({r['candidate_landing_page_id']for r in output})==4,
         'ONE_CANDIDATE_PAGE_PER_CAMPAIGN_REQUIRED')
    return {'schema':'bsre-four-entry-review-proposal-v1','mode':'REVIEW_ONLY_NO_APPLY',
            'input_sha256':dict(sorted(pins.items())),'account_id':'573-038-4686',
            'campaigns':output,'candidate_campaign_count':4,'source_page_count':native['page_count'],
            'source_family_counts':native['family_counts'],'source_registry_modified':False,
            'source_routes_modified':False,'aggregate_average_daily_budget_aed_proposed':2000,
            'vat_included':False,'normal_overdelivery_accepted':True,'old_campaign_reactivation_supported':False,
            'apply_supported':False,'website_publication_authorized':False,'tracking_changes_authorized':False,
            'ads_changes_authorized':False,'ads_activation_authorized':False,'spending_authorized':False,
            'scope_limit':'Candidate selection only. Public CMS identities do not prove campaign metadata ownership, freshness at release, route reconciliation, factual approval or combined acceptance. Preserve all360source slots and the separate300brief/640catalogue scope; review CMP competition before any binding.'}


def build_proposal(root=ROOT):return compile_proposal(*load_inputs(root))


def verify_saved(root=ROOT):
    with(root/OUTPUT).open('rb')as stream:blob=stream.read(MAX_BYTES+1)
    need(len(blob)<=MAX_BYTES,'PROPOSAL_BYTE_BOUND')
    need(same(json.loads(blob.decode('utf-8')),build_proposal(root)),'PROPOSAL_DIFFERS_FROM_CURRENT_INPUTS')
    return {'passed':True,'candidate_campaigns':4,'source_pages':360,'aggregate_average_daily_budget_aed_proposed':2000,
            'apply_supported':False,'publication_or_ads_authorized':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',required=True)
    parser.parse_args()
    try:print(json.dumps(verify_saved(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'passed':False,'code':'ENTRY_COHORT_PROPOSAL_HELD','error_type':type(error).__name__,'apply_supported':False}));raise SystemExit(1)
