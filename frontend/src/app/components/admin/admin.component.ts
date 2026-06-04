import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService, UserRecord } from '../../services/auth.service';

type Role = 'admin' | 'viewer';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  private auth = inject(AuthService);
  readonly currentUser = this.auth.user;

  users = signal<UserRecord[]>([]);
  loading = signal(true);
  listError = signal<string | null>(null);

  // Create user form
  newUsername = '';
  newPassword = '';
  newRole: Role = 'viewer';
  createError = signal<string | null>(null);
  createSuccess = signal<string | null>(null);
  creating = signal(false);

  // Change own password form
  newOwnPassword = '';
  confirmOwnPassword = '';
  pwError = signal<string | null>(null);
  pwSuccess = signal<string | null>(null);
  pwSaving = signal(false);

  ngOnInit() { this.loadUsers(); }

  loadUsers() {
    this.loading.set(true);
    this.listError.set(null);
    this.auth.listUsers().subscribe({
      next: r => { this.users.set(r.users || []); this.loading.set(false); },
      error: err => {
        this.listError.set(err?.error?.error || 'Failed to load users');
        this.loading.set(false);
      },
    });
  }

  createUser() {
    this.createError.set(null);
    this.createSuccess.set(null);
    if (!this.newUsername.trim() || !this.newPassword) {
      this.createError.set('Username and password required');
      return;
    }
    this.creating.set(true);
    this.auth.createUser(this.newUsername.trim(), this.newPassword, this.newRole).subscribe({
      next: u => {
        this.creating.set(false);
        this.createSuccess.set(`User "${u.username}" created`);
        this.newUsername = '';
        this.newPassword = '';
        this.newRole = 'viewer';
        this.loadUsers();
      },
      error: err => {
        this.creating.set(false);
        this.createError.set(err?.error?.error || 'Failed to create user');
      },
    });
  }

  deleteUser(u: UserRecord) {
    if (u.username === this.currentUser()?.username) return;
    if (!confirm(`Delete user "${u.username}"?`)) return;
    this.auth.deleteUser(u.username).subscribe({
      next: () => this.loadUsers(),
      error: err => alert(err?.error?.error || 'Failed to delete user'),
    });
  }

  changeMyPassword() {
    this.pwError.set(null);
    this.pwSuccess.set(null);
    if (!this.newOwnPassword) { this.pwError.set('Password required'); return; }
    if (this.newOwnPassword.length < 8) { this.pwError.set('Password must be at least 8 characters'); return; }
    if (this.newOwnPassword !== this.confirmOwnPassword) { this.pwError.set('Passwords do not match'); return; }
    this.pwSaving.set(true);
    this.auth.changeOwnPassword(this.newOwnPassword).subscribe({
      next: () => {
        this.pwSaving.set(false);
        this.pwSuccess.set('Password updated');
        this.newOwnPassword = '';
        this.confirmOwnPassword = '';
      },
      error: err => {
        this.pwSaving.set(false);
        this.pwError.set(err?.error?.error || 'Failed to change password');
      },
    });
  }

  isSelf(u: UserRecord): boolean {
    return u.username === this.currentUser()?.username;
  }
}
