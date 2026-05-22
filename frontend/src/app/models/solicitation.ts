export interface Solicitation {
  id: string;
  agencyId: string;
  title: string;
  description: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface SolicitationCreate {
  agencyId: string;
  title: string;
  description: string;
  status?: string;
}
