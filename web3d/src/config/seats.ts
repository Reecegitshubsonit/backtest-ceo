/** Agent seats around the table. Angle 0 faces the viewer; seats skip the front so the table stays visible. */
export interface Seat { id: string; name: string; job: string; angleDeg: number }

export const SEATS: Seat[] = [
  { id: 'scanner', name: 'SCANNER AGENT', job: 'Surfacing candidates', angleDeg: -38 },
  { id: 'strategist', name: 'STRATEGIST', job: 'Writing strategy rules', angleDeg: -82 },
  { id: 'backtester', name: 'BACKTESTER', job: 'Running tests', angleDeg: -128 },
  { id: 'auditor', name: 'VALIDATION AUDITOR', job: 'Checking results', angleDeg: 128 },
  { id: 'regime', name: 'REGIME ANALYST', job: 'Labelling conditions', angleDeg: 82 },
  { id: 'risk', name: 'RISK MANAGER', job: 'Limits and veto', angleDeg: 38 },
]
