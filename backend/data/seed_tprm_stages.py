"""
backend/data/seed_tprm_stages.py

One-time seed for the assessment_stages reference table. Run once after
migration:

    python -m data.seed_tprm_stages

Idempotent: skips insertion if rows already exist for a given
(direction, stage_number) pair.
"""

import asyncio
from core.database import AsyncSessionLocal  # matches existing project convention
from core.tprm import AssessmentStage, Direction
from sqlalchemy import select

EGRESS_STAGES = [
    (1, "Data classification and scoping",
     "Establish what data is leaving, how sensitive it is, and how often, before anything is sent. This determines how strict every downstream control needs to be.",
     "What fields are included? What classification level applies? What volume/frequency? Can fields be minimized or masked? Does this touch regulated data (HIPAA/GDPR/PCI)?",
     "Data classification worksheet; field-level data flow description; minimization justification; regulatory mapping"),
    (2, "Transfer method determination",
     "Confirm whether the vendor receives data via file transfer or API, since that choice determines which control set applies from here on.",
     "File or API, and why? Supported protocols? Who initiates? Required format/schema? Any size limits?",
     "Vendor technical specification; architecture diagram; written protocol confirmation"),
    (3, "Secure transport (encryption in transit)",
     "All outbound data must be encrypted in motion -- SFTP/FTPS for files, TLS 1.2+ for APIs. Plain FTP/HTTP is never acceptable.",
     "Is a secure protocol confirmed? Deprecated TLS versions disabled? Certificate validation enforced? mTLS available for high-sensitivity data?",
     "Protocol confirmation or endpoint scan; TLS configuration evidence; certificate details"),
    (4, "Authentication (file transfer)",
     "The vendor must be able to verify files genuinely came from us, using SSH key pairs rather than passwords, which can be guessed or stolen.",
     "Key-based auth in place, password auth disabled? Key type/length? How was the public key exchanged? Rotation schedule?",
     "Endpoint config showing password auth disabled; key exchange record; rotation policy"),
    (5, "Credential and secrets management",
     "Private keys and tokens must live in an approved secrets vault, never embedded in code or config files -- this addresses non-human identity (service account/key) risk.",
     "Where is the key/secret stored? Which systems can retrieve it, and is retrieval logged? Automated rotation configured? Anomaly alerts in place?",
     "Vault entry/access policy; access log sample; rotation policy; service account inventory entry"),
    (6, "Managed file transfer (MFT) platform",
     "Internal systems should never connect directly to a vendor; an MFT platform sits in the middle as a controlled, logged checkpoint.",
     "Is an MFT platform in use, or is this scripted ad hoc? Does it log every transfer? Retry/failure alerting? Who administers it?",
     "MFT configuration for this vendor route; sample transfer logs; admin access control list"),
    (7, "Scheduling, automation, and approval gates",
     "Transfers should run on a fixed automated schedule; sensitive data should require a human approval gate before release.",
     "Is the schedule automated and documented? Is there a manual approval step for sensitive data, and who approves? Retry/alert behavior on failure?",
     "Job schedule configuration; approval workflow and approver list; sample approval record"),
    (8, "Vendor allowlisting and connection pre-authorization",
     "Before the first transfer, both sides agree on exactly which account, key, and IP range is expected, so unexpected traffic is denied by default.",
     "Has the vendor allowlisted our account/key/IP? Are transfer times, directories, and naming conventions agreed in writing?",
     "Written connection specification; vendor allowlisting confirmation; successful connection test record"),
    (9, "Monitoring, logging, and alerting",
     "Every transfer must be visible -- who sent what, when, and whether it succeeded -- both for troubleshooting and for audit evidence.",
     "Are all transfers logged with full detail? Are alerts configured for failures or anomalies? Retention period for logs? Fed into the SIEM?",
     "Sample logs (success and failure); alert configuration; log retention policy"),
    (10, "Encryption at rest (both sides)",
     "Data must also be encrypted while stored, both on our staging systems and on the vendor's systems after arrival; key ownership determines who can decrypt it.",
     "Is our staging data encrypted at rest? Does the vendor encrypt at rest, and to what standard? Who holds the encryption keys?",
     "SOC 2 report or security whitepaper excerpt on encryption at rest; key management description; our own at-rest config"),
    (11, "Data retention and secure deletion",
     "Data should only exist as long as there's a business or compliance reason; both sides must commit to a defined retention period and verifiable secure deletion.",
     "What's our retention period and deletion method? What's the vendor's? Can they certify deletion on request?",
     "Retention schedule and deletion configuration; vendor's documented policy; sample deletion certificate"),
    (12, "Incident response and breach notification",
     "Both parties must agree in advance on how fast a breach is reported and what detail is shared, since controls reduce risk but don't eliminate it.",
     "What's the vendor's contractual notification window (target 24-48 hrs)? What detail will they share? Who bears remediation costs?",
     "Breach notification clause from contract/DPA; vendor IR process summary; internal IR playbook reference"),
    (13, "Compliance and contractual enforcement",
     "Every technical control above must be enforceable in writing -- encryption standards, protocols, retention, breach notification, audit rights.",
     "Does the contract mandate the controls above? Do we hold audit rights? Is a current SOC 2 Type II / ISO 27001 report on file?",
     "Executed contract/DPA; current certification reports; signed risk acceptance for any deviations"),
]

INGRESS_STAGES = [
    (1, "Data classification and scoping (inbound)",
     "Classify what the vendor is sending back before it arrives -- inbound data can be more sensitive than what was sent out.",
     "What is being returned, and at what classification level? Any new sensitive elements introduced? Expected volume/frequency?",
     "Data classification entry; field-level description from vendor docs; volume/frequency baseline"),
    (2, "Ingress method determination",
     "Determine whether data returns via file or API, since API ingress actively expands our attack surface and demands stronger validation on our side.",
     "File or API, who initiates? Confirm SFTP/FTPS only for files. Which endpoints receive API calls, and are they exposed only to this vendor?",
     "Vendor integration spec for the return path; network diagram; endpoint exposure review"),
    (3, "Input validation",
     "Inbound data is never trusted blindly -- every payload is checked against schema, size, and injection patterns before acceptance.",
     "Is schema/type validation enforced? Volume/size sanity checks? Screening for injection patterns? What happens on failure?",
     "Validation rule set/schema; sample validation failure and quarantine record; failure alert configuration"),
    (4, "Source authentication",
     "Verify inbound data genuinely comes from the authorized vendor -- signature verification for files, token validation for APIs.",
     "Is the vendor's signature verified on every file? Is token validation enforced at the gateway? Are failures logged and alerted?",
     "Signature/token validation configuration; vendor credential registration record; failed-auth log sample"),
    (5, "Rate limiting and throttling",
     "Cap how much a vendor can send in a given window, protecting our systems from a compromised or misconfigured vendor flooding us with traffic.",
     "Are rate limits configured and based on an expected baseline? What response does the vendor get when throttled? Are breaches alerted?",
     "Rate limit configuration; documented thresholds; sample throttling event/alert"),
    (6, "Staging and quarantine",
     "Inbound data lands first in an isolated staging zone for validation and malware scanning -- never directly into production.",
     "Does all inbound data land in isolated staging first? What checks run there? How long does promotion take, and who approves it?",
     "Staging architecture description; promotion workflow/approval record; malware scan configuration"),
    (7, "Encryption (inbound, in transit and at rest)",
     "Inbound transport must be encrypted, and the staging zone itself must encrypt data at rest.",
     "Is all inbound transport encrypted with modern protocols? Is staging encrypted at rest? Who manages those keys?",
     "TLS configuration of receiving endpoint; at-rest encryption config for staging; key management reference"),
    (8, "Access controls (RBAC and least privilege)",
     "Once data lands, only roles with genuine need may touch it; staged data should be read-only with every access logged.",
     "Is RBAC enforced with documented roles? Is staged data read-only until promotion? Is every access logged and periodically recertified?",
     "RBAC role matrix; access log samples; most recent access certification record"),
    (9, "Retention and lifecycle management (inbound)",
     "Define how long inbound vendor data lives in our environment, driven by business need and regulation, with traceable secure deletion at expiry.",
     "What retention period applies, and is deletion automated? What does the vendor retain on their side, and how do they delete it?",
     "Retention schedule; automated deletion config/log; vendor retention/deletion policy"),
    (10, "Monitoring, logging, and alerting (inbound)",
     "Maintain full visibility over inbound flows -- arrivals, validation outcomes, access, and deletions -- with anomaly alerts against a documented baseline.",
     "Are all inbound events logged end to end? Are anomaly alerts configured against baseline volume/timing? Fed into the SIEM?",
     "Sample inbound activity logs; alert rule configuration; SIEM integration evidence"),
    (11, "Incident response (inbound scenarios)",
     "Plan specifically for vendor-originated failure modes: a breached vendor sending malicious data, cross-customer contamination, or a flood defeating rate limits.",
     "Does the IR playbook explicitly cover vendor-originated incidents? Can processing be halted and quarantined immediately? Vendor's notification obligation?",
     "IR playbook section for third-party incidents; kill-switch/halt procedure; vendor notification obligations from contract"),
    (12, "Compliance and contractual enforcement (inbound)",
     "Contractually bind the vendor to inbound expectations: no cross-customer commingling, timely notification, defined retention, and liability allocation.",
     "Does the contract prohibit data commingling and mandate encrypted return transport? Does the vendor carry cyber liability insurance?",
     "Contract/DPA clauses for inbound flow; vendor insurance certificate; current certification reports"),
    (13, "Continuous monitoring and periodic reassessment",
     "Vendor security isn't a one-time gate -- reassess at least annually, sooner if risk indicators change, with spot audits of live data and access logs.",
     "Is there a defined reassessment cadence? Are refreshed certifications collected each cycle? Is there a trigger for out-of-cycle reassessment?",
     "Reassessment schedule and last completed record; spot audit workpapers; out-of-cycle trigger criteria"),
]


async def seed():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AssessmentStage.direction, AssessmentStage.stage_number))
        existing_keys = set(existing.all())

        rows_added = 0
        for direction, stage_list in ((Direction.EGRESS, EGRESS_STAGES), (Direction.INGRESS, INGRESS_STAGES)):
            for stage_number, title, guidance, questions, evidence in stage_list:
                if (direction, stage_number) in existing_keys:
                    continue
                db.add(AssessmentStage(
                    direction=direction,
                    stage_number=stage_number,
                    title=title,
                    guidance=guidance,
                    review_questions=questions,
                    evidence_to_collect=evidence,
                ))
                rows_added += 1

        await db.commit()
        print(f"Seed complete: {rows_added} stage rows added.")


if __name__ == "__main__":
    asyncio.run(seed())
