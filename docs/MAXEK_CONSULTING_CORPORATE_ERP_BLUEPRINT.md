# MAXEK Consulting Corporate ERP Blueprint

## Purpose

MAXEK Consulting ERP is a construction consultancy management system for Quantity Surveying, Estimation, Tendering, Planning, Cost Control and Project Management services.

The system should support the complete consultancy cycle from enquiry to tender submission, project award support, project planning, cost monitoring, billing and management reporting.

## Corporate Positioning

**Product name:** MAXEK ERP  
**Business focus:** Construction Estimation, Tendering and Planning Consultancy  
**Primary users:** Consulting team, estimators, quantity surveyors, planners, project managers, accounts team, management and clients  
**Project types:** Roads, highways, bridges, buildings, infrastructure, industrial and commercial projects

## Core ERP Modules

### 1. Lead and Client Management

Purpose: Track business enquiries, client details, consultancy packages, fee proposals and conversion status.

Key functions:

- Client master
- Lead and enquiry register
- Project value and consultancy fee calculation
- Package selection: Estimation, Estimation + Tender, Estimation + Tender + Planning
- Proposal status tracking
- Follow-up reminders
- Client-wise project history

Core outputs:

- Consultancy proposal
- Fee quotation
- Client project summary
- Lead conversion report

### 2. Project Master

Purpose: Maintain one controlled project record for every consultancy assignment.

Key functions:

- Project code generation
- Project category: Road, Bridge, Building, Infrastructure, Industrial, Commercial
- Client, location, project value and package mapping
- Drawing/document register
- Assigned QS, estimator, planner and reviewer
- Project stage tracking

Core outputs:

- Project profile
- Assignment sheet
- Project status dashboard

### 3. Tender Review

Purpose: Review tender documents before estimation and bid preparation.

Key functions:

- Tender document checklist
- Scope summary
- BOQ availability status
- Drawing availability status
- Technical eligibility notes
- Commercial condition notes
- Risk and clarification register
- Go/no-go recommendation

Core outputs:

- Tender review sheet
- Tender risk register
- Clarification list

### 4. Drawing and Document Control

Purpose: Control drawings, revisions and tender documents used for quantity take-off.

Key functions:

- Drawing register
- Revision tracking
- Document category tagging
- Received date and source
- Approval/use status
- Attachment management

Core outputs:

- Drawing register
- Pending drawing list
- Revision history

### 5. Quantity Surveying and Take-Off

Purpose: Prepare structured quantity measurements for roads, bridges, buildings and other works.

Key functions:

- Quantity take-off sheets
- Measurement sheets
- Item-wise quantity build-up
- Unit conversion
- BOQ item mapping
- Quantity verification workflow
- Reviewer approval

Project format libraries:

- Road: Earthwork, GSB, WMM, prime coat, tack coat, DBM, BC, drainage, retaining wall, protection works, road furniture, traffic signage, road marking, utilities, overheads, profit
- Bridge: Survey, excavation, foundation, pile works, pile cap, pier, abutment, wing wall, deck slab, crash barrier, expansion joint, bearing, approach slab, drainage, finishing, overheads, profit
- Building: Site clearance, excavation, PCC, footing, column, beam, slab, reinforcement, masonry, plastering, flooring, painting, doors/windows, water supply, drainage, electrical, fire fighting, HVAC, external works, overheads, profit

Core outputs:

- Quantity take-off sheet
- BOQ sheet
- Quantity verification report

### 6. BOQ and Detailed Estimation

Purpose: Build project cost estimates from quantities, rates, overheads and profit margins.

Key functions:

- BOQ preparation
- Detailed estimate
- Material cost estimation
- Labour cost estimation
- Equipment cost estimation
- Overhead calculation
- Profit margin calculation
- Cost summary
- Version control for estimate revisions

Core outputs:

- Detailed estimate
- Project cost summary
- Tender cost summary
- Revision comparison

### 7. Rate Analysis

Purpose: Maintain defensible rates for material, labour, machinery and productivity.

Key functions:

- Material analysis
- Labour analysis
- Machinery analysis
- Productivity assumptions
- Market rate verification
- Rate library by location/project type
- Rate approval workflow

Core outputs:

- Rate analysis sheet
- Material requirement sheet
- Labour requirement sheet
- Equipment requirement sheet

### 8. Tender Management

Purpose: Manage commercial and technical bid preparation up to submission support.

Key functions:

- Tender checklist
- BOQ verification
- Commercial bid preparation
- Technical bid preparation
- Tender cost sheet
- Submission document tracker
- Bid submission support status
- Post-submission clarification tracker

Core outputs:

- Commercial bid
- Technical bid checklist
- Tender cost sheet
- Tender submission register

### 9. Planning and Scheduling

Purpose: Convert estimated scope into execution planning outputs.

Key functions:

- Project schedule
- Work breakdown structure
- Resource planning
- Equipment planning
- Procurement planning
- Cash flow planning
- Milestone tracking

Core outputs:

- Construction schedule
- Resource plan
- Equipment plan
- Procurement plan
- Cash flow statement

### 10. Cost Control and Profitability

Purpose: Monitor budget, cost, profitability and variance throughout consultancy and project support.

Key functions:

- Budget preparation
- Budget monitoring
- Cost monitoring
- Budget vs actual analysis
- Profitability analysis
- Package-wise revenue tracking
- Client billing status

Core outputs:

- Budget vs actual report
- Profitability analysis
- Cost control dashboard
- Management MIS

### 11. Accounts and Billing

Purpose: Track consultancy charges, payment terms and client billing.

Key functions:

- Consultancy fee setup
- Payment milestones: 50% advance, 40% draft submission, 10% final submission
- Invoice/bill tracking
- Receipt tracking
- Outstanding report
- Project-wise revenue report

Core outputs:

- Consultancy invoice tracker
- Payment collection report
- Outstanding statement

### 12. Workflow and Approvals

Purpose: Keep professional control over estimation quality and tender deliverables.

Recommended workflow:

1. Tender Review
2. Drawing Review
3. Quantity Take-Off
4. BOQ Preparation
5. Rate Analysis
6. Cost Estimation
7. Resource Planning
8. Cash Flow Planning
9. Tender Submission
10. Project Award Support

Approval gates:

- Tender review approval
- Quantity verification approval
- Rate analysis approval
- Estimate approval
- Bid document approval
- Final submission approval

## User Roles

- Super Admin
- Management
- Business Development
- Project Manager
- Quantity Surveyor
- Estimator
- Planning Engineer
- Tender Executive
- Accounts Executive
- Document Controller
- Client Viewer

## Standard Dashboards

### Management Dashboard

- Active projects
- Tender submissions this month
- Consultancy revenue
- Pending receivables
- Estimate value under preparation
- Package-wise revenue
- Project profitability
- Delayed submissions

### Estimation Dashboard

- Pending take-offs
- BOQs under preparation
- Rate analysis pending approval
- Estimates due this week
- Revision requests

### Tender Dashboard

- Tenders under review
- Submission deadlines
- Commercial bid status
- Technical bid status
- Clarifications pending

### Planning Dashboard

- Schedules under preparation
- Resource plans pending
- Cash flow plans pending
- Milestone plan status

## Master Data

Required masters:

- Company master
- Client master
- Project master
- Project type master
- Package master
- BOQ item library
- Material master
- Labour category master
- Equipment master
- Unit master
- Rate library
- Overhead and profit templates
- User and role master
- Approval matrix

## Reports and Deliverables

Standard deliverables:

- BOQ sheet
- Quantity take-off sheet
- Rate analysis sheet
- Material requirement sheet
- Labour requirement sheet
- Equipment requirement sheet
- Project cost summary
- Cash flow statement
- Construction schedule
- Tender cost summary
- Profitability analysis

Management reports:

- Project status report
- Fee proposal report
- Tender pipeline report
- Estimate revision report
- Budget vs actual report
- Receivable report
- Profitability report

## Consultancy Fee Logic

The ERP should support both package-based and project-value-based fee calculation.

Package fee bands:

- Estimation Package: Rs. 25,000 to Rs. 75,000
- Estimation + Tender Package: Rs. 75,000 to Rs. 2,00,000
- Estimation + Tender + Planning: Rs. 1,00,000 to Rs. 5,00,000

Project value fee guide:

- Up to Rs. 1 Crore: Rs. 25,000 to Rs. 50,000
- Rs. 1 Crore to Rs. 5 Crore: Rs. 50,000 to Rs. 1,50,000
- Rs. 5 Crore to Rs. 25 Crore: Rs. 1,50,000 to Rs. 5,00,000
- Rs. 25 Crore to Rs. 100 Crore: Rs. 5,00,000 to Rs. 15,00,000
- Above Rs. 100 Crore: Negotiable

## MVP Build Priority

### Phase 1: Consultancy Core

- Client master
- Project master
- Package and fee proposal
- Tender review
- Drawing/document register
- BOQ and quantity take-off
- Rate analysis
- Estimate summary
- Basic approval workflow

### Phase 2: Tender and Planning

- Commercial bid preparation
- Technical bid checklist
- Tender submission tracker
- Project schedule
- Resource planning
- Procurement planning
- Cash flow planning

### Phase 3: Corporate Control

- Cost control dashboard
- Budget vs actual analysis
- Profitability analysis
- Client billing and receipts
- Management MIS
- Client portal
- Document version control

### Phase 4: Advanced Features

- AI assisted BOQ drafting
- Auto rate suggestions from rate library
- Drawing-based QTO support
- Excel import/export automation
- PDF proposal generation
- Mobile review/approval

## Immediate Implementation Recommendation

The existing MAXEK ERP already contains many foundations: clients, projects, BOQ, DPR, billing, accounts, payroll, stores, treasury, reports and command centre. The next practical step is to create a dedicated **Consultancy Command Centre** that groups the consultancy workflow into:

- Enquiries and proposals
- Tender review
- QTO and BOQ
- Rate analysis
- Estimation
- Tender submission
- Planning
- Billing and profitability

This approach keeps the system corporate, focused and usable while extending the current ERP instead of rebuilding from zero.
