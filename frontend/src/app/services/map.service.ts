import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import * as M from '../models/models';

@Injectable({ providedIn: 'root' })
export class MapService {
  private api = '/api/map';
  constructor(private http: HttpClient) {}

  listFloors(): Observable<{ floors: M.FloorSummary[] }> {
    return this.http.get<{ floors: M.FloorSummary[] }>(`${this.api}/floors`);
  }
  getFloor(id: string): Observable<M.Floor> {
    return this.http.get<M.Floor>(`${this.api}/floors/${id}`);
  }
  createFloor(body: { name: string; building: string; image: string }): Observable<M.Floor> {
    return this.http.post<M.Floor>(`${this.api}/floors`, body);
  }
  updateFloor(
    id: string,
    body: Partial<{ name: string; building: string; order: number; image: string }>,
  ): Observable<M.Floor> {
    return this.http.put<M.Floor>(`${this.api}/floors/${id}`, body);
  }
  deleteFloor(id: string): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(`${this.api}/floors/${id}`);
  }
  getPlacements(id: string): Observable<{ floor_id: string; placements: M.ApPlacement[] }> {
    return this.http.get<{ floor_id: string; placements: M.ApPlacement[] }>(
      `${this.api}/floors/${id}/placements`,
    );
  }
  savePlacements(id: string, placements: M.ApPlacement[]): Observable<any> {
    return this.http.put(`${this.api}/floors/${id}/placements`, { placements });
  }
}
