"""Curated Philippine complaint-routing guidance; simulated service actions only."""
GUIDANCE={
    'version':'PH-2026-10-13',
    'steps':[
        'Direct urgent account-security concerns to the financial institution through independently verified official channels.',
        'Capture the complaint reference, disputed transaction IDs, dates, amounts, recipient, customer narrative and available supporting records.',
        'Separate what the customer reports from ledger facts. A successful PIN or OTP does not by itself establish informed intent or legal liability.',
        'Propose institution-led account-security, transfer-recall or disputed-funds verification actions for analyst review. Never promise a refund or execute a bank hold from this simulator.',
        'Use the institution’s Financial Consumer Protection Assistance Mechanism first. If dissatisfied with its action or response, prepare escalation through BSP-CAM/BOB with the earlier complaint reference and supporting record.',
        'Record the decision, remaining evidence gaps and next update. Do not invent a statutory resolution deadline or treat customer distress as proof of fraud.'
    ],
    'do_not_collect':['PIN','password','OTP','full card security code'],
    'sources':[
        {'id':'BSP-CAM-2025','url':'https://www.bsp.gov.ph/Inclusive%20Finance/How-to-file-a-complaint-with-BSP-CAM-Sep2025.pdf'},
        {'id':'BSP-1215-2025','url':'https://www.bsp.gov.ph/Regulations/Published%20Issuances/Images/Circular_1215.pdf'},
        {'id':'BSP-FCP','url':'https://www.bsp.gov.ph/Pages/InclusiveFinance/ConsumerAssistanceChannelsChatbot.aspx'},
        {'id':'GCASH-SCAM','url':'https://help.gcash.com/hc/fil/articles/4413295284377-Report-a-scam'},
        {'id':'BPI-FCPAM','url':'https://www.bpi.com.ph/about-bpi/governance/financial-consumer-protection'}
    ],
    'source_limit':'BSP indexed official summaries informed routing; full BSP PDF extraction was blocked. Provider pages were read directly. No legal deadline or provider-specific refund entitlement is encoded.',
    'limits':'Routing and evidence checklist for a synthetic prototype. Institution-specific procedures, eligibility and legal determinations require a qualified analyst.'
}
