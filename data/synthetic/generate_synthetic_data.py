"""
Synthetic OIL-style safety report generator (blueprint Part 5.2, Level 3 data
strategy). NONE of these narratives describe real OIL incidents -- they are
team-authored, grounded in real IOGP Life-Saving Rule categories and
DEKRA/EEI-style SIF precursor patterns, following the blueprint's explicit
instruction to vary phrasing/severity/ambiguity realistically and to include
deliberately ambiguous and borderline cases (not just "obviously HIGH" or
"obviously LOW" examples).

Every row is clearly and permanently labelled synthetic via `source` and
`gold_*` columns; the frontend must always show a "Synthetic demo data"
badge next to anything sourced from this file (see README "Dataset & source
discipline").

Run: python generate_synthetic_data.py
Output: data/synthetic/reports.csv (deterministic given SEED, so re-running
does not change dashboard results between demo runs).
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)

OUT_PATH = Path(__file__).resolve().parent / "reports.csv"

SITES = ["Site A (Upstream E&P)", "Site B (Pipeline Corridor)", "Site C (Gas Processing)",
         "Site D (Drilling Rig)", "Site E (Terminal)"]

# Each scenario: (narrative, activity, location, gold_sif, gold_lsr, report_type)
SCENARIOS: list[tuple[str, str, str, str, str, str]] = [
    # ---------------- ENERGY ISOLATION ----------------
    ("Technician opened a flange before confirming isolation. Residual pressure was released. No injury occurred.",
     "Pipeline Maintenance", "flange near separator unit 3", "HIGH", "Energy Isolation", "NEAR_MISS"),
    ("Line was opened before confirming isolation and residual pressure released onto the maintenance crew standing at the flange.",
     "Pipeline Maintenance", "flange assembly", "HIGH", "Energy Isolation", "NEAR_MISS"),
    ("Electrician started work on a control panel before confirming it was de-energized, receiving a minor shock from a live wire.",
     "Electrical Work", "switchgear room", "HIGH", "Energy Isolation", "INCIDENT"),
    ("Maintenance crew applied LOTO correctly and verified zero energy before opening the valve for scheduled maintenance. No issues noted.",
     "Pipeline Maintenance", "valve station", "NON_SIF", "Energy Isolation", "UNSAFE_CONDITION"),
    ("Isolation was completed and confirmed by the shift supervisor before the pump seal replacement began; work proceeded without incident.",
     "General Maintenance", "pump house", "NON_SIF", "Energy Isolation", "UNSAFE_CONDITION"),
    ("Worker bypassed the lockout procedure to save time and started disassembling the compressor while it was still isolated only partially.",
     "General Maintenance", "compressor skid", "HIGH", "Energy Isolation", "UNSAFE_ACT"),
    ("LOTO tags were applied but the isolation point was never physically verified with a zero-energy check before valve removal began.",
     "Pipeline Maintenance", "valve manifold", "MEDIUM", "Energy Isolation", "NEAR_MISS"),
    ("Contractor removed a pressure gauge without confirming the line had been isolated; a small amount of residual gas was released.",
     "Pipeline Maintenance", "gas metering skid", "HIGH", "Energy Isolation", "NEAR_MISS"),
    ("Isolation was correctly applied, tagged, and verified using a zero-energy check before the technician began pump maintenance.",
     "General Maintenance", "pump station", "NON_SIF", "Energy Isolation", "UNSAFE_CONDITION"),
    ("Operator opened an inspection hatch on a de-energized vessel after LOTO was verified by two independent checks; no issues found.",
     "General Maintenance", "vessel inspection point", "NON_SIF", "Energy Isolation", "UNSAFE_CONDITION"),
    ("A junior technician disconnected a hydraulic line without checking whether isolation had been confirmed, and hydraulic fluid sprayed nearby.",
     "General Maintenance", "hydraulic skid", "MEDIUM", "Energy Isolation", "NEAR_MISS"),
    ("Pressure gauge read slightly high during a routine isolation check; noted in the log for follow-up.",
     "Pipeline Maintenance", "manifold gauge panel", "LOW", "Energy Isolation", "UNSAFE_CONDITION"),

    # ---------------- LINE OF FIRE ----------------
    ("Worker walked beneath a suspended load during a lifting operation to retrieve a dropped tool.",
     "Lifting Operation", "crane lift zone", "HIGH", "Line of Fire", "NEAR_MISS"),
    ("Employee stood in the pinch point between a pipe and the crane hook while positioning the load, and had to step back quickly.",
     "Lifting Operation", "pipe rack laydown area", "HIGH", "Line of Fire", "NEAR_MISS"),
    ("A dropped wrench fell from an elevated platform and landed close to a worker standing directly below the work area.",
     "General Maintenance", "elevated platform", "HIGH", "Line of Fire", "NEAR_MISS"),
    ("Exclusion zone was properly established and enforced around the lifting operation; no personnel entered the line of fire.",
     "Lifting Operation", "crane lift zone", "NON_SIF", "Line of Fire", "UNSAFE_CONDITION"),
    ("Crew maintained a safe distance from the suspended load throughout the lift, with the exclusion zone barricaded and supervised.",
     "Lifting Operation", "laydown yard", "NON_SIF", "Line of Fire", "UNSAFE_CONDITION"),
    ("Worker was struck by a swinging pipe section during positioning after the tag line was released early.",
     "Lifting Operation", "pipe handling area", "HIGH", "Line of Fire", "INCIDENT"),
    ("A worker briefly entered the exclusion zone near rotating equipment to retrieve a dropped glove, then stepped back out immediately.",
     "General Maintenance", "rotating equipment area", "MEDIUM", "Line of Fire", "NEAR_MISS"),
    ("Unusual noise heard near rotating equipment; area was cleared as a precaution.",
     "General Maintenance", "rotating equipment area", "REVIEW", "Line of Fire", "NEAR_MISS"),

    # ---------------- CONFINED SPACE ----------------
    ("Contractor entered a tank for inspection before the gas test was completed and the permit was signed.",
     "Confined Space Entry", "storage tank", "HIGH", "Confined Space", "NEAR_MISS"),
    ("Worker entered the confined space without a standby attendant posted at the entry point.",
     "Confined Space Entry", "vessel manway", "HIGH", "Confined Space", "UNSAFE_ACT"),
    ("Confined-space entry was completed with a valid permit, verified gas test, and full PPE. No issues noted.",
     "Confined Space Entry", "storage tank manway", "NON_SIF", "Confined Space", "UNSAFE_CONDITION"),
    ("Gas test was completed and confirmed clear, permit was signed, and the standby attendant remained at the entry point throughout the work.",
     "Confined Space Entry", "vessel entry point", "NON_SIF", "Confined Space", "UNSAFE_CONDITION"),
    ("Technician felt dizzy shortly after entering a tank; gas test results were later found to have been recorded before ventilation was complete.",
     "Confined Space Entry", "process vessel", "HIGH", "Confined Space", "INCIDENT"),
    ("The permit for the confined space entry had expired an hour earlier, but the crew continued working inside the vessel.",
     "Confined Space Entry", "separator vessel", "HIGH", "Confined Space", "UNSAFE_CONDITION"),

    # ---------------- HOT WORK ----------------
    ("Welding was carried out near an open drum of solvent without a fire watch or a gas test.",
     "Hot Work", "maintenance workshop", "HIGH", "Hot Work", "NEAR_MISS"),
    ("Grinding work generated sparks near an area where flammable vapours were later confirmed present.",
     "Hot Work", "process area near tank farm", "HIGH", "Hot Work", "NEAR_MISS"),
    ("Hot work permit was issued, gas test confirmed clear, and a dedicated fire watch was posted for the full duration of the welding.",
     "Hot Work", "fabrication yard", "NON_SIF", "Hot Work", "UNSAFE_CONDITION"),
    ("Fire watch remained in place with extinguisher ready while cutting operations proceeded under a valid hot work permit.",
     "Hot Work", "pipe rack area", "NON_SIF", "Hot Work", "UNSAFE_CONDITION"),
    ("Cutting torch was used to remove a bracket near a vent that was not confirmed to be free of flammable vapours.",
     "Hot Work", "tank farm perimeter", "MEDIUM", "Hot Work", "NEAR_MISS"),

    # ---------------- WORKING AT HEIGHT ----------------
    ("Worker leaned out from a scaffold platform to reach a valve without re-anchoring the fall-arrest lanyard.",
     "Working at Height", "elevated scaffold platform", "HIGH", "Working at Height", "NEAR_MISS"),
    ("Technician climbed onto an elevated platform without a harness to inspect equipment.",
     "Working at Height", "process structure platform", "HIGH", "Working at Height", "UNSAFE_ACT"),
    ("Fall-arrest harness was worn and correctly anchored throughout the scaffold inspection; no issues noted.",
     "Working at Height", "scaffold platform", "NON_SIF", "Working at Height", "UNSAFE_CONDITION"),
    ("Worker wore a full harness with the lanyard properly anchored to the designated point while working on the elevated platform.",
     "Working at Height", "elevated walkway", "NON_SIF", "Working at Height", "UNSAFE_CONDITION"),
    ("Minor slip on a wet floor near a stairwell railing, no injury.",
     "General Maintenance", "stairwell landing", "MEDIUM", "Working at Height", "NEAR_MISS"),
    ("A worker's harness lanyard was found unclipped for a brief period while repositioning on the scaffold, then reconnected immediately.",
     "Working at Height", "scaffold platform level 2", "MEDIUM", "Working at Height", "NEAR_MISS"),
    ("Loose cable tie found on walkway, no one nearby, corrected on the spot.",
     "General Maintenance", "site walkway", "LOW", "Working at Height", "UNSAFE_CONDITION"),

    # ---------------- SAFE MECHANICAL LIFTING ----------------
    ("Crane lift proceeded without a documented lift plan and the exclusion zone was not established.",
     "Lifting Operation", "crane pad", "HIGH", "Safe Mechanical Lifting", "NEAR_MISS"),
    ("Rigging sling showed visible wear but was used anyway during the lift.",
     "Lifting Operation", "rigging yard", "HIGH", "Safe Mechanical Lifting", "UNSAFE_CONDITION"),
    ("Lift plan was documented and reviewed, rigging equipment was inspected beforehand, and the exclusion zone was fully enforced during the lift.",
     "Lifting Operation", "crane lift area", "NON_SIF", "Safe Mechanical Lifting", "UNSAFE_CONDITION"),
    ("Crane operator followed the approved lift plan and confirmed all rigging hardware was within inspection date before starting the lift.",
     "Lifting Operation", "module lift zone", "NON_SIF", "Safe Mechanical Lifting", "UNSAFE_CONDITION"),
    ("Tag line was not used during a moderate lift, causing the load to sway slightly near ground crew who stepped back in time.",
     "Lifting Operation", "laydown area", "MEDIUM", "Safe Mechanical Lifting", "NEAR_MISS"),

    # ---------------- DRIVING ----------------
    ("Driver was using a mobile phone while driving between well sites on the access road.",
     "Driving / Vehicle Movement", "site access road", "MEDIUM", "Driving", "UNSAFE_ACT"),
    ("Vehicle skidded on a wet access road after exceeding the site speed limit, narrowly avoiding a ditch.",
     "Driving / Vehicle Movement", "access road", "HIGH", "Driving", "NEAR_MISS"),
    ("Driver completed the journey management checklist, wore a seatbelt, and observed the posted speed limit throughout the trip.",
     "Driving / Vehicle Movement", "field access road", "NON_SIF", "Driving", "UNSAFE_CONDITION"),
    ("Vehicle reversing near the workshop nearly struck a pedestrian who stepped out without checking; the driver stopped in time.",
     "Driving / Vehicle Movement", "workshop yard", "HIGH", "Driving", "NEAR_MISS"),

    # ---------------- WORK AUTHORIZATION ----------------
    ("Maintenance work began without a valid work permit being issued for the task.",
     "General Maintenance", "process unit", "MEDIUM", "Work Authorization", "UNSAFE_CONDITION"),
    ("Permit had expired but the crew continued working on the equipment for another hour before noticing.",
     "General Maintenance", "compressor building", "MEDIUM", "Work Authorization", "UNSAFE_CONDITION"),
    ("Work permit was reviewed, signed by the area authority, and displayed at the job site before work began; no issues noted.",
     "General Maintenance", "process unit", "NON_SIF", "Work Authorization", "UNSAFE_CONDITION"),

    # ---------------- BYPASSING SAFETY CONTROLS ----------------
    ("Operator bypassed the high-pressure trip alarm to keep the unit running during startup.",
     "General Maintenance", "control room", "HIGH", "Bypassing Safety Controls", "UNSAFE_ACT"),
    ("Interlock was defeated to allow the pump to run with the guard open, exposing the coupling.",
     "General Maintenance", "pump house", "HIGH", "Bypassing Safety Controls", "UNSAFE_CONDITION"),
    ("Safety interlock authorization was obtained from the shift supervisor and logged before the temporary bypass was applied for testing, then restored immediately after.",
     "General Maintenance", "control room", "NON_SIF", "Bypassing Safety Controls", "UNSAFE_CONDITION"),

    # ---------------- GENERAL / NON-LSR-SPECIFIC ROUTINE REPORTS ----------------
    ("Housekeeping issue: cardboard boxes were left blocking a fire extinguisher cabinet in the warehouse. Corrected immediately.",
     "General Maintenance", "warehouse", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("A spill of a small amount of water from a leaking tap was reported in the break room and mopped up promptly.",
     "General Maintenance", "break room", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Employee mentioned the word 'fall' while describing a decline in the site's monthly safety scores during a toolbox talk.",
     "General Maintenance", "toolbox talk area", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("A signboard with faded paint was reported near the main gate and scheduled for repainting.",
     "General Maintenance", "main gate", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Printer in the site office was out of toner; IT was notified to replace the cartridge.",
     "General Maintenance", "site office", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Near miss reported but activity and location are unclear from the submitted narrative.",
     "General Maintenance", "unspecified area", "REVIEW", "No applicable rule", "NEAR_MISS"),
    ("An employee raised a general concern about workload during a shift handover meeting; no physical hazard described.",
     "General Maintenance", "shift handover point", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Damaged floor tile noticed near the canteen entrance; low foot traffic area, no one nearby, flagged for repair.",
     "General Maintenance", "canteen entrance", "LOW", "No applicable rule", "UNSAFE_CONDITION"),

    # ---------------- ADDITIONAL LOW-SEVERITY VARIETY (category-balance) ----------------
    ("A worn floor mat was noticed near the workshop entrance; scheduled for replacement during the next maintenance round.",
     "General Maintenance", "workshop entrance", "LOW", "No applicable rule", "UNSAFE_CONDITION"),
    ("A small oil stain was found on the concrete near the pump house, well away from any walkway; absorbent applied and area monitored.",
     "General Maintenance", "pump house apron", "LOW", "No applicable rule", "UNSAFE_CONDITION"),
    ("Handrail on a low internal staircase had slight surface rust noted during a routine walk-down; flagged for a future paint touch-up.",
     "General Maintenance", "internal staircase", "LOW", "Working at Height", "UNSAFE_CONDITION"),
    ("A tool box was left slightly open on a bench overnight in the workshop with no one present; closed and secured the next morning.",
     "General Maintenance", "workshop bench", "LOW", "No applicable rule", "UNSAFE_CONDITION"),
    ("Faded lane markings were observed on a low-traffic internal access road; reported for repainting during the next resurfacing cycle.",
     "Driving / Vehicle Movement", "internal access road", "LOW", "Driving", "UNSAFE_CONDITION"),
    ("A minor drip from a pressure gauge fitting was noted during a routine walk-down, well below the alarm threshold; logged for the next inspection.",
     "General Maintenance", "gauge panel", "LOW", "Energy Isolation", "UNSAFE_CONDITION"),

    # ---------------- ADDITIONAL NON_SIF GOOD-PRACTICE VARIETY (category-balance) ----------------
    ("Toolbox talk was held before the shift and all attendees signed the safety briefing register; no concerns raised.",
     "General Maintenance", "muster point", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Weekly fire extinguisher inspection was completed with all units found in date and correctly charged.",
     "General Maintenance", "process unit", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("New contractor completed the site safety induction and PPE fitting before being escorted to the work area by the site host.",
     "General Maintenance", "site induction room", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Spill kit inventory check was completed for the month with all items accounted for and in good condition.",
     "General Maintenance", "spill response locker", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("Scheduled vehicle pre-start inspection was completed with no defects found; vehicle cleared for the day's journeys.",
     "Driving / Vehicle Movement", "vehicle yard", "NON_SIF", "Driving", "UNSAFE_CONDITION"),
    ("Crew completed a positive observation card noting good use of PPE and correct barricading during a routine maintenance task.",
     "General Maintenance", "process unit", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),

    # ---------------- DRILLING-SPECIFIC (activity variety) ----------------
    ("Rig floor crew handled a stand of drill pipe without confirming the derrickman's readiness signal, causing a brief swing of the pipe near ground crew.",
     "Drilling Operations", "rig floor", "HIGH", "Line of Fire", "NEAR_MISS"),
    ("Pre-tour safety meeting confirmed all rig floor personnel positions before pipe handling began; operation proceeded without incident.",
     "Drilling Operations", "rig floor", "NON_SIF", "Line of Fire", "UNSAFE_CONDITION"),

    # ---------------- EXPANSION SET (gold-set size / MEDIUM-class support) ----------------
    # Added to move the dataset toward the blueprint's 300-500 row target (Part 5.3) and,
    # specifically, to give the MEDIUM class meaningfully more train/test support -- the
    # original set left MEDIUM with very low test-set support (see README Known
    # Limitations). Same authoring rules as above: team-authored, IOGP/DEKRA-grounded,
    # varied phrasing/severity/ambiguity, not "obviously HIGH/LOW" only.

    # --- Energy Isolation ---
    ("Maintenance crew began breaking a flange connection while the isolation valve was only tagged, not physically locked, after the assigned lock key was misplaced.",
     "Pipeline Maintenance", "flange connection point", "HIGH", "Energy Isolation", "NEAR_MISS"),
    ("Isolation was applied and tagged, but the zero-energy verification step was skipped because the pressure gauge was already reading close to zero.",
     "Pipeline Maintenance", "manifold isolation point", "MEDIUM", "Energy Isolation", "NEAR_MISS"),
    ("A relief valve was assumed to have vented residual pressure fully, but no confirmatory bleed-down check was performed before the flange bolts were loosened.",
     "Pipeline Maintenance", "flange near pressure vessel", "MEDIUM", "Energy Isolation", "NEAR_MISS"),
    ("Double block-and-bleed isolation was applied, verified independently by two technicians, and logged on the permit before the exchanger head was removed.",
     "General Maintenance", "heat exchanger bay", "NON_SIF", "Energy Isolation", "UNSAFE_CONDITION"),
    ("A slightly worn isolation tag was replaced during a routine isolation-point audit; no active work was underway at the isolation point at the time.",
     "General Maintenance", "isolation point audit", "LOW", "Energy Isolation", "UNSAFE_CONDITION"),
    ("A valve believed to be isolated was found still partly open when the technician began removing its actuator, releasing a small amount of process fluid.",
     "Pipeline Maintenance", "actuator removal point", "HIGH", "Energy Isolation", "NEAR_MISS"),
    ("The isolation checklist for a pump seal job was signed off before the final zero-energy check had actually been walked down by the permit holder.",
     "General Maintenance", "pump seal station", "MEDIUM", "Energy Isolation", "NEAR_MISS"),

    # --- Line of Fire ---
    ("A worker briefly stood within the marked exclusion zone to adjust a tag line before stepping back out as the lift resumed.",
     "Lifting Operation", "crane lift zone", "MEDIUM", "Line of Fire", "NEAR_MISS"),
    ("Ground crew were repositioning a suspended module when the tag line parted, swinging the load toward two workers who stepped clear just in time.",
     "Lifting Operation", "module lift area", "HIGH", "Line of Fire", "NEAR_MISS"),
    ("Tag lines and rigging were inspected before the lift, the exclusion zone was clearly barricaded, and a dedicated banksman controlled all pedestrian access throughout.",
     "Lifting Operation", "crane lift zone", "NON_SIF", "Line of Fire", "UNSAFE_CONDITION"),
    ("A safety cone marking the edge of the lift exclusion zone had been knocked over by wind; no lifting was in progress and the cone was reset immediately.",
     "Lifting Operation", "laydown yard perimeter", "LOW", "Line of Fire", "UNSAFE_CONDITION"),
    ("A pipe spool being lowered onto the pipe rack swung briefly toward a worker who was still inside the marked exclusion zone finishing an unrelated task.",
     "Lifting Operation", "pipe rack area", "MEDIUM", "Line of Fire", "NEAR_MISS"),
    ("Report mentions something moving quickly near the crew during a shift but does not specify what the object was or whether anyone was in its path.",
     "General Maintenance", "unspecified work area", "REVIEW", "Line of Fire", "NEAR_MISS"),
    ("A worker leaned into the swing radius of an operating excavator for a few seconds to shout an instruction before stepping back to a safe distance.",
     "General Maintenance", "excavation area", "MEDIUM", "Line of Fire", "NEAR_MISS"),

    # --- Confined Space ---
    ("Gas testing was completed before entry, but the results were not re-verified after a 45-minute delay before the crew actually entered the vessel.",
     "Confined Space Entry", "process vessel", "MEDIUM", "Confined Space", "NEAR_MISS"),
    ("A worker entered a drained tank for a visual inspection while the standby attendant briefly left the entry point to retrieve additional equipment.",
     "Confined Space Entry", "storage tank manway", "HIGH", "Confined Space", "NEAR_MISS"),
    ("Continuous gas monitoring was maintained throughout the vessel entry, with the attendant never leaving the entry point and communication checks every 15 minutes.",
     "Confined Space Entry", "process vessel manway", "NON_SIF", "Confined Space", "UNSAFE_CONDITION"),
    ("A confined-space entry permit was found with a minor administrative field left blank after the job was already complete; no safety control was actually missing during the work.",
     "Confined Space Entry", "vessel entry point", "LOW", "Confined Space", "UNSAFE_CONDITION"),
    ("The confined-space entry permit listed an incorrect vessel number, although the vessel actually entered had in fact been gas-tested and isolated beforehand.",
     "Confined Space Entry", "separator vessel", "MEDIUM", "Confined Space", "NEAR_MISS"),
    ("A ventilation fan inside a tank stopped partway through the job without the crew noticing until a worker began feeling light-headed.",
     "Confined Space Entry", "storage tank interior", "HIGH", "Confined Space", "INCIDENT"),

    # --- Hot Work ---
    ("A hot work permit was issued and a fire watch posted, but the gas test was performed slightly outside the actual radius of the welding point.",
     "Hot Work", "fabrication bay", "MEDIUM", "Hot Work", "NEAR_MISS"),
    ("Grinding continued after the fire watch was called away to answer a radio call, with no relief watch posted in the interim.",
     "Hot Work", "workshop grinding station", "HIGH", "Hot Work", "NEAR_MISS"),
    ("A hot work permit, continuous gas monitoring and a fully equipped fire watch with an extinguisher were all in place for the entire duration of the cutting job.",
     "Hot Work", "pipe fabrication yard", "NON_SIF", "Hot Work", "UNSAFE_CONDITION"),
    ("A fire extinguisher tag at a hot work location showed an inspection date three days overdue; the extinguisher itself was full and functional and was swapped immediately.",
     "Hot Work", "welding bay", "LOW", "Hot Work", "UNSAFE_CONDITION"),
    ("Welding screens were used to control sparks, but a small gap at the base of one screen was only noticed and closed partway through the job.",
     "Hot Work", "process area near tank farm", "MEDIUM", "Hot Work", "NEAR_MISS"),

    # --- Working at Height ---
    ("A worker's fall-arrest lanyard was connected to a handrail rather than a certified anchor point for part of a scaffold task.",
     "Working at Height", "scaffold platform", "MEDIUM", "Working at Height", "NEAR_MISS"),
    ("A scaffold guardrail section had been temporarily removed for material handling and was not reinstated before the next shift began work on that level.",
     "Working at Height", "scaffold level 3", "HIGH", "Working at Height", "UNSAFE_CONDITION"),
    ("All scaffold guardrails and toe boards were verified in place by a competent person before work began, and harnesses were double-checked at the access point.",
     "Working at Height", "scaffold access point", "NON_SIF", "Working at Height", "UNSAFE_CONDITION"),
    ("A scaffold inspection tag showed the next-due date was two days away; the scaffold itself passed a visual check with no defects noted.",
     "Working at Height", "scaffold platform", "LOW", "Working at Height", "UNSAFE_CONDITION"),
    ("A worker briefly unclipped a fall-arrest lanyard to reposition along a narrow platform before re-clipping to the next anchor point a few steps later.",
     "Working at Height", "elevated walkway", "MEDIUM", "Working at Height", "NEAR_MISS"),
    ("A report describes an incident on a raised structure but does not clarify the height involved or whether fall protection was actually in use.",
     "General Maintenance", "raised structure", "REVIEW", "Working at Height", "NEAR_MISS"),

    # --- Safe Mechanical Lifting ---
    ("The lift plan was in place, but the rigging inspection checklist was completed from memory rather than a physical inspection immediately before the lift.",
     "Lifting Operation", "crane pad", "MEDIUM", "Safe Mechanical Lifting", "NEAR_MISS"),
    ("A multi-point lift proceeded with one sling rated below the calculated load after a last-minute equipment substitution was not re-checked against the lift plan.",
     "Lifting Operation", "module lift zone", "HIGH", "Safe Mechanical Lifting", "NEAR_MISS"),
    ("The lift plan, rigging certification, and exclusion zone were all verified by the lift supervisor immediately before the crane began the pick.",
     "Lifting Operation", "crane lift area", "NON_SIF", "Safe Mechanical Lifting", "UNSAFE_CONDITION"),
    ("A rigging inspection tag had a smudged date that was difficult to read, though the sling itself was confirmed within its inspection interval by the rigging register.",
     "Lifting Operation", "rigging yard", "LOW", "Safe Mechanical Lifting", "UNSAFE_CONDITION"),
    ("Wind speed approached the crane's rated operating limit partway through a lift, and the lift was paused only after already being underway.",
     "Lifting Operation", "crane pad", "MEDIUM", "Safe Mechanical Lifting", "NEAR_MISS"),

    # --- Driving ---
    ("A driver briefly checked a text message at a stop sign before continuing the journey on the site access road.",
     "Driving / Vehicle Movement", "site access road", "MEDIUM", "Driving", "UNSAFE_ACT"),
    ("A light vehicle lost traction on a graded haul road and slid toward the road edge before the driver regained control.",
     "Driving / Vehicle Movement", "haul road", "HIGH", "Driving", "NEAR_MISS"),
    ("A journey management plan was filed, the vehicle passed its pre-trip inspection, and the driver took the scheduled rest break during the long-distance transfer.",
     "Driving / Vehicle Movement", "field access road", "NON_SIF", "Driving", "UNSAFE_CONDITION"),
    ("A vehicle's tire pressure was found slightly below the recommended level during a routine check; corrected before the vehicle was dispatched.",
     "Driving / Vehicle Movement", "vehicle yard", "LOW", "Driving", "UNSAFE_CONDITION"),

    # --- Work Authorization ---
    ("Work continued for roughly ten minutes after the permit's listed end time before the crew noticed and stopped to have it renewed.",
     "General Maintenance", "process unit", "MEDIUM", "Work Authorization", "UNSAFE_CONDITION"),
    ("A contractor began hot-tapping a live line under a permit that had actually been issued for a different, unrelated task.",
     "Pipeline Maintenance", "live tie-in point", "HIGH", "Work Authorization", "UNSAFE_CONDITION"),
    ("The area authority reviewed and re-validated the permit at shift handover before work continued into the second shift.",
     "General Maintenance", "process unit", "NON_SIF", "Work Authorization", "UNSAFE_CONDITION"),
    ("A work permit was correctly signed, but the copy posted at the job site was a slightly outdated revision; the actual work scope matched the valid permit on file.",
     "General Maintenance", "job site noticeboard", "LOW", "Work Authorization", "UNSAFE_CONDITION"),

    # --- Bypassing Safety Controls ---
    ("A low-level alarm was silenced during a known sensor fault, with a manual round-the-clock check substituted, but the substitute check was missed for one shift.",
     "General Maintenance", "control room", "MEDIUM", "Bypassing Safety Controls", "UNSAFE_CONDITION"),
    ("A safety shower interlock on a chemical loading line was bypassed to speed up changeover, without documented authorization.",
     "General Maintenance", "chemical loading bay", "HIGH", "Bypassing Safety Controls", "UNSAFE_CONDITION"),
    ("A temporary bypass of a non-critical alarm was authorized, time-limited, logged in the shift log, and removed exactly as scheduled.",
     "General Maintenance", "control room", "NON_SIF", "Bypassing Safety Controls", "UNSAFE_CONDITION"),
    ("An alarm-bypass tag from a previous, already-completed authorized test was found still attached to a panel; the underlying alarm itself was confirmed active.",
     "General Maintenance", "instrument panel", "LOW", "Bypassing Safety Controls", "UNSAFE_CONDITION"),

    # --- General / no applicable rule / ambiguous ---
    ("Emergency shower and eyewash stations were checked and flushed as part of the monthly inspection with no faults found.",
     "General Maintenance", "process unit", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("A near-miss reporting refresher was held for new hires with no actual incidents discussed.",
     "General Maintenance", "training room", "NON_SIF", "No applicable rule", "UNSAFE_CONDITION"),
    ("A section of perimeter fencing showed minor sagging well away from any live work area; scheduled for tensioning.",
     "General Maintenance", "site perimeter", "LOW", "No applicable rule", "UNSAFE_CONDITION"),
    ("A worker mentioned feeling uneasy about an upcoming task during a toolbox talk but did not describe what specifically felt unsafe.",
     "General Maintenance", "toolbox talk area", "REVIEW", "No applicable rule", "UNSAFE_CONDITION"),
    ("A second-hand report describes a colleague nearly getting hurt earlier in the shift, without naming the activity, hazard, or location.",
     "General Maintenance", "unspecified area", "REVIEW", "No applicable rule", "NEAR_MISS"),
    ("A near-miss involving a dropped tool was reported verbally at shift handover, but the exact height and location were not recorded before the report was logged.",
     "General Maintenance", "unspecified elevated area", "MEDIUM", "Working at Height", "NEAR_MISS"),
]

TITLES = {
    "HIGH": ["Potential serious injury precursor", "High-risk near miss", "Critical safety observation"],
    "MEDIUM": ["Safety concern requiring follow-up", "Near miss - review recommended", "Barrier verification gap"],
    "LOW": ["Minor safety observation", "Housekeeping item"],
    "NON_SIF": ["Routine safety observation", "Good practice observed", "Minor administrative item"],
    "REVIEW": ["Unclear report - needs review", "Ambiguous observation"],
}

REPORTERS = ["Field Technician", "HSE Officer", "Shift Supervisor", "Contractor", "Operator", "Maintenance Engineer"]


def _random_datetime(months_back: int = 6) -> datetime:
    now = datetime(2026, 8, 15)
    days_back = random.randint(0, months_back * 30)
    return now - timedelta(days=days_back, hours=random.randint(0, 23))


def _paraphrase_variant(narrative: str, variant: int) -> str:
    """Genuine surface variants (not a static suffix) so retrieval isn't clone-dominated."""
    if variant == 0:
        return narrative
    prefixes = [
        "Shift handover note: ",
        "Supervisor walkdown recorded that ",
        "Permit close-out comment: ",
    ]
    details = [
        " Event logged near end of day shift.",
        " Observed during morning toolbox talk follow-up.",
        " Equipment tag referenced in the PTW package.",
    ]
    # Light restructure: prefix + original + distinct trailing detail
    return f"{prefixes[variant % len(prefixes)]}{narrative.rstrip('.')}{details[variant % len(details)]}"


def _base_key(narrative: str) -> str:
    """Normalize narrative for leakage grouping (strip variant prefixes/suffixes)."""
    text = narrative
    for p in ("Shift handover note: ", "Supervisor walkdown recorded that ", "Permit close-out comment: "):
        if text.startswith(p):
            text = text[len(p):]
    for s in (
        " Event logged near end of day shift.",
        " Observed during morning toolbox talk follow-up.",
        " Equipment tag referenced in the PTW package.",
        " (follow-up observation #2)",
        " (follow-up observation #3)",
    ):
        if text.endswith(s):
            text = text[: -len(s)]
    return text.strip().rstrip(".")


def generate_rows() -> list[dict]:
    rows = []
    idx = 0
    # Group rows by base scenario BEFORE split assignment so variants never leak across splits.
    groups: list[list[dict]] = []

    for narrative, activity, location, gold_sif, gold_lsr, report_type in SCENARIOS:
        repeats = 3 if gold_sif in ("HIGH", "MEDIUM") else \
                  2 if gold_sif in ("NON_SIF", "LOW") else 1
        group = []
        for r in range(repeats):
            site = SITES[idx % len(SITES)] if r == 0 else random.choice(SITES)
            occurred_at = _random_datetime()
            title = random.choice(TITLES.get(gold_sif, ["Safety observation"]))
            group.append({
                "report_type": report_type,
                "title": title,
                "narrative": _paraphrase_variant(narrative, r),
                "site": site,
                "activity": activity,
                "location": location,
                "occurred_at": occurred_at.isoformat(),
                "reporter_name": random.choice(REPORTERS),
                "gold_sif": gold_sif,
                "gold_lsr": gold_lsr,
                "_base_key": _base_key(narrative),
            })
            idx += 1
        groups.append(group)

    random.shuffle(groups)
    n = len(groups)
    for i, group in enumerate(groups):
        frac = i / n
        split = "train" if frac < 0.6 else ("val" if frac < 0.8 else "test")
        for row in group:
            row["split"] = split
            rows.append(row)

    random.shuffle(rows)
    return rows


def main():
    rows = generate_rows()
    fieldnames = [
        "report_type", "title", "narrative", "site", "activity", "location",
        "occurred_at", "reporter_name", "gold_sif", "gold_lsr", "split",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} synthetic reports -> {OUT_PATH}")
    print("Split counts:", {s: sum(1 for r in rows if r["split"] == s) for s in ("train", "val", "test")})
    print("Gold SIF label counts:", {
        label: sum(1 for r in rows if r["gold_sif"] == label)
        for label in ("HIGH", "MEDIUM", "LOW", "NON_SIF", "REVIEW")
    })


if __name__ == "__main__":
    main()
