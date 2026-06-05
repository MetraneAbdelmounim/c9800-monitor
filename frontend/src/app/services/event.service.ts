import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { EventList } from '../models/models';

@Injectable({ providedIn: 'root' })
export class EventService {
  private api = '/api/events';
  constructor(private http: HttpClient) {}

  list(showAcked: boolean): Observable<EventList> {
    return this.http.get<EventList>(`${this.api}?show_acked=${showAcked}`);
  }
  ack(ids: string[]): Observable<{ acked: number }> {
    return this.http.post<{ acked: number }>(`${this.api}/ack`, { ids });
  }
  ackAll(): Observable<{ acked: number }> {
    return this.http.post<{ acked: number }>(`${this.api}/ack-all`, {});
  }
}
