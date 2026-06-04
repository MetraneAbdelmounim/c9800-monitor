import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { ApListComponent } from './components/ap-list/ap-list.component';
import { ClientListComponent } from './components/client-list/client-list.component';
import { ClientExperienceComponent } from './components/client-experience/client-experience.component';
import { WlanListComponent } from './components/wlan-list/wlan-list.component';
import { SystemInfoComponent } from './components/system-info/system-info.component';
import { ClientTrackingComponent } from './components/client-tracking/client-tracking.component';
import { RoamingGraphComponent } from './components/roaming-graph/roaming-graph.component';
import { ApMapComponent } from './components/ap-map/ap-map.component';
import { LoginComponent } from './components/login/login.component';
import { AdminComponent } from './components/admin/admin.component';
import { SettingsComponent } from './components/settings/settings.component';
import { ProfileComponent } from './components/profile/profile.component';
import { authGuard, adminGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
  { path: 'access-points', component: ApListComponent, canActivate: [authGuard] },
  { path: 'map', component: ApMapComponent, canActivate: [authGuard] },
  { path: 'clients', component: ClientListComponent, canActivate: [authGuard] },
  { path: 'client-experience', component: ClientExperienceComponent, canActivate: [authGuard] },
  { path: 'wlans', component: WlanListComponent, canActivate: [authGuard] },
  { path: 'system', component: SystemInfoComponent, canActivate: [authGuard] },
  { path: 'roaming-graph', component: RoamingGraphComponent, canActivate: [authGuard] },
  { path: 'tracking', component: ClientTrackingComponent, canActivate: [authGuard] },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'admin', component: AdminComponent, canActivate: [adminGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [adminGuard] },
  { path: '**', redirectTo: 'dashboard' },
];
