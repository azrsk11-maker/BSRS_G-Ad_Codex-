# Dubai seller and landlord content research

Draft for factual and scope review under issues #1 and #2. On 8 November 2026, the existing seller and landlord enquiry routes returned HTTP 200 on direct GET. The status check establishes route availability only. These modules are proposed content for review. Their eventual placement depends on the dedicated-page and historical crosswalk decisions.

## Seller module

### Preparing to sell a Dubai property

Start with the details that shape a sale discussion. Tell us the building or community, property type, whether the property is occupied, and when you would like to sell. Mention any existing mortgage or tenancy so the next conversation can address the circumstances of your property. Use the enquiry form for initial details. Keep identity documents and title records for a verified secure channel.

If you need a formal property valuation certificate, check Dubai Land Department’s separate valuation service. The department lists residential units and villas among the property types it handles. [DLD Property Valuation](https://dubailand.gov.ae/en/eservices/property-valuation)

Draft call to action: **Discuss selling your property**. [Existing seller enquiry route](https://blackswanrealestate.ae/enquire/sell/)

## Landlord module

### Preparing to let a Dubai property

Tell us where the property is, its type and size, and when it will be available. If it is already let, mention the tenancy end date. Tell us whether you want to discuss a new letting or have a question about an existing tenancy. Share contract numbers and supporting documents only through a verified secure channel.

For an existing tenancy, Dubai Land Department’s Rental Index has inputs for contract end date, property type and current annual rent. Its tenancy registration service explains the available Ejari channels and requirements. Use the official pages to check which route applies to your situation. [DLD Rental Index](https://dubailand.gov.ae/en/eservices/rental-index/?r=1), [DLD tenancy registration and renewal](https://dubailand.gov.ae/en/eservices/register-renew-ejari-contract/)

Draft call to action: **Discuss letting your property**. [Existing landlord enquiry route](https://blackswanrealestate.ae/enquire/let/)

## Keyword research handoff

The following are authored seed phrases for a targeted Dubai Planner batch. Their sources establish an official task and help distinguish its intent. Search demand, provider identity, company remit and campaign scope still require evidence. The proposed exact match type is for conflict simulation only.

| Seed phrase | Research disposition and source |
|---|---|
| dld property valuation certificate application | Official-service intent hypothesis. [Property Valuation](https://dubailand.gov.ae/en/eservices/property-valuation) |
| dubai rest property valuation certificate download | Official-service intent hypothesis. [Property Valuation](https://dubailand.gov.ae/en/eservices/property-valuation) |
| dld rental valuation certificate application | Official-service intent hypothesis. [Rental Valuation](https://dubailand.gov.ae/en/eservices/request-for-valuation-of-property-lease) |
| dubai land department rental index calculator | Official-tool intent hypothesis. [Rental Index](https://dubailand.gov.ae/en/eservices/rental-index/?r=1) |
| dubai rest renew ejari contract online | Official-service intent hypothesis. [Tenancy registration and renewal](https://dubailand.gov.ae/en/eservices/register-renew-ejari-contract/) |
| dubai rest cancel ejari contract online | Official-service intent hypothesis. [DLD service directory](https://dubailand.gov.ae/en/eservices/name-of-services/) |
| dubai rest register tenancy contract online | Official-service intent hypothesis. [Tenancy registration and renewal](https://dubailand.gov.ae/en/eservices/register-renew-ejari-contract/) |
| dubai now terminate tenancy contract online | Official-service intent hypothesis. [Dubai Now tenancy service](https://dubailand.gov.ae/en/eservices/register-renew-terminate-tenancy-contract/) |

The existing lexical matcher found zero exact collisions against the 570 explicitly protected rows in the 7,705-row Planner proposal file and these five mixed-intent controls:

- sell my villa in dubai with a broker
- dubai landlord agent to find tenants
- property valuation before selling my dubai apartment
- help letting my apartment and registering ejari
- dubai rental index advice before letting my property

The eight seeds have zero normalized duplicates in that proposal file (SHA256 `e5e5375f451eb8c92b721105efe8cdadf72d4c9101ddae58e96a66adc9a307e5`). These are lexical diagnostics for the tested corpus. Keep ambiguous valuation, Ejari and rent-index phrases held for intent review. Each master gains zero admitted rows from this batch.

Before release, confirm the responsible reviewer, permitted service remit, accurate page placement and any use of inventory or asset rights. Keep the approved cohort and campaign-level exclusion scope separate from this draft.

## Historical Keyword Planner readback

On 8 November 2026, Real Estate account 573-038-4686 returned all eight submitted phrases in a historical metrics export. The UI showed United Arab Emirates, all languages and Google. The CSV covers 1 October 2025 through 30 September 2026. The research UI automatically saved a Planner plan. No campaign was created or edited.

- Dubai Land Department rental index calculator returned 40 average monthly searches, Low competition and competition index 6. The monthly values were 40, 20, 30, 40, 40, 30, 70, 40, 50, 50, 40 and 20. These are provider estimates for the observed settings.
- The other seven exact seeds had blank volume, competition and bid fields. Blank values remain unknown. The result does not establish owner acquisition intent or justify excluding the calculator phrase across the account.
- All eight remain held for business and scope review. Zero approved, deployed or master keyword rows were added.

Private source export is Keyword Stats 2026-11-08 at 22_48_18.csv with SHA256 e9ef5ce0d9da17f0be870171126d020a5aa95f94a5f3a8c95f4721237456797d. Local validation matched all eight keywords against the submitted seeds and confirmed exactly one populated average. The raw export and account-specific columns stay outside the repository.

## Exclusion scope review

The eight long phrases can describe public self-service tasks. A landlord or seller can also search for those tasks while seeking representation. Keep the eight phrases on hold. Do not promote their shorter fragments into shared or account-level exclusions. If an owner service review later confirms a specific self-service task is outside a specific campaign's remit, assess the full phrase as a campaign-scoped exact candidate against the complete reviewed protected corpus.

The existing lexical matcher was run against these authored, mixed-intent controls. Every fragment matched its control under both phrase and broad simulation. No fragment matched its control under exact simulation.

| Fragment | Protected-intent control |
|---|---|
| property valuation certificate | sell my apartment after getting a property valuation certificate |
| rental valuation certificate | find an agent to let my villa after getting a rental valuation certificate |
| rental index calculator | find a landlord agent after using the dubai land department rental index calculator |
| renew ejari | find a letting agent who can help me renew ejari |
| cancel ejari | need a landlord agent to relet after i cancel ejari |
| register tenancy contract | need a letting agent to register tenancy contract and find tenants |
| terminate tenancy contract | need a letting agent after i terminate tenancy contract |

These controls demonstrate the risk of broadening exclusions. They are synthetic and do not establish Google matching behavior, deployed overlap, or sufficient corpus coverage.
