"""
WTT (Wissenstransfer) Template v1

This template defines the canonical WTT guideline structure for Vorhabensbeschreibung documents.
Based on the WTT guidelines with sections 1-4 and all required subheadings.
"""

from typing import Dict, Any
import json


def get_wtt_v1_template() -> Dict[str, Any]:
    """
    Returns the WTT v1 template structure with concise section titles.

    Structure:
    - Section 1: Information about the company (1.1, 1.2, 1.3)
    - Section 2: Technical concept, objective, and content (2.1 through 2.7)
    - Section 3: Prospects for success (3.1 through 3.7)
    - Section 4: Milestone planning (4.1) with structured table

    Returns:
        Dictionary with "sections" key containing list of section definitions
    """
    return {
        "sections": [
            # Section 1: Information about the company
            {
                "id": "1",
                "title": "1. Angaben zum Unternehmen",
                "content": "",
                "type": "text"
            },
            {
                "id": "1.1",
                "title": "1.1. Unternehmensangaben",
                "content": "",
                "type": "text"
            },
            {
                "id": "1.2",
                "title": "1.2. Unternehmensgeschichte (kurz)",
                "content": "",
                "type": "text"
            },
            {
                "id": "1.3",
                "title": "1.3. Branche und Leistungsangebot",
                "content": "",
                "type": "text"
            },

            # Section 2: Technical concept, objective, and content
            {
                "id": "2",
                "title": "2. Technisches Konzept, Zielsetzung und Projektinhalt",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.1",
                "title": "2.1. Geschäfts-/Investitionskonzept",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.2",
                "title": "2.2. Produkt- bzw. Prozessinnovation und Innovationsgrad (Stand der Technik)",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.3",
                "title": "2.3. Aufgaben und Arbeitspakete des Beraters",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.4",
                "title": "2.4. Umsetzungszeitplan und Innovationsunterstützungsleistungen",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.5",
                "title": "2.5. Notwendigkeit des WTT-Vorhabens",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.6",
                "title": "2.6. Temporäres finanzielles Risiko ohne Förderung",
                "content": "",
                "type": "text"
            },
            {
                "id": "2.7",
                "title": "2.7. Beitrag zur Vernetzung entlang der Wertschöpfungskette",
                "content": "",
                "type": "text"
            },

            # Section 3: Prospects for success
            {
                "id": "3",
                "title": "3. Erfolgsaussichten des Vorhabens",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.1",
                "title": "3.1. Erreichbarkeit der Projektziele",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.2",
                "title": "3.2. Anwendungsorientierung",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.3",
                "title": "3.3. Umsetzungsrelevanz",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.4",
                "title": "3.4. Wettbewerbssituation",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.5",
                "title": "3.5. Marktfähigkeit nach Projektabschluss",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.6",
                "title": "3.6. Verwertung, Amortisation und Beschäftigungseffekte",
                "content": "",
                "type": "text"
            },
            {
                "id": "3.7",
                "title": "3.7. Interessensbekundungen und Anfragen",
                "content": "",
                "type": "text"
            },

            # Section 4: Milestone planning
            {
                "id": "4",
                "title": "4. Meilensteinplanung",
                "content": "",
                "type": "text"
            },
            {
                "id": "4.1",
                "title": "4.1. Meilensteinplanung",
                "content": json.dumps({
                    "milestones": [],
                    "total_expenditure": None
                }),
                "type": "milestone_table"
            }
        ]
    }
