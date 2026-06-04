import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface AuthUser {
  username: string;
  role: 'admin' | 'viewer';
  must_change_password?: boolean;
}

export interface UserRecord {
  username: string;
  role: 'admin' | 'viewer';
  must_change_password?: boolean;
  created_at?: string;
}

interface LoginResponse {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = 'wlc.token';
const USER_KEY = 'wlc.user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = '/api/auth';

  private _user = signal<AuthUser | null>(this.readUser());
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);

  constructor(private http: HttpClient) {}

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.api}/login`, { username, password }).pipe(
      tap(res => this.persist(res.token, res.user))
    );
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this._user.set(null);
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  hasRole(role: 'admin' | 'viewer'): boolean {
    const u = this._user();
    return !!u && u.role === role;
  }

  mustChangePassword(): boolean {
    return !!this._user()?.must_change_password;
  }

  /** Re-fetch the user state from /me and update the local signal. */
  refreshMe(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${this.api}/me`).pipe(
      tap(u => {
        this._user.set(u);
        localStorage.setItem(USER_KEY, JSON.stringify(u));
      })
    );
  }

  // ── Admin / user-management endpoints ────────────────
  listUsers(): Observable<{ total: number; users: UserRecord[] }> {
    return this.http.get<{ total: number; users: UserRecord[] }>(`${this.api}/users`);
  }

  createUser(username: string, password: string, role: 'admin' | 'viewer'): Observable<UserRecord> {
    return this.http.post<UserRecord>(`${this.api}/register`, { username, password, role });
  }

  deleteUser(username: string): Observable<{ ok: boolean; deleted: string }> {
    return this.http.delete<{ ok: boolean; deleted: string }>(`${this.api}/users/${encodeURIComponent(username)}`);
  }

  changeOwnPassword(newPassword: string): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.api}/change-password`, { new_password: newPassword });
  }

  private persist(token: string, user: AuthUser): void {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    this._user.set(user);
  }

  private readUser(): AuthUser | null {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }
}
