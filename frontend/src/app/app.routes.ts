import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { OverviewComponent } from './components/overview/overview.component';
import { ApListComponent } from './components/ap-list/ap-list.component';
import { ClientListComponent } from './components/client-list/client-list.component';
import { ClientExperienceComponent } from './components/client-experience/client-experience.component';
import { WlanListComponent } from './components/wlan-list/wlan-list.component';
import { SystemInfoComponent } from './components/system-info/system-info.component';
import { ClientTrackingComponent } from './components/client-tracking/client-tracking.component';
import { RoamingGraphComponent } from './components/roaming-graph/roaming-graph.component';
import { ApMapComponent } from './components/ap-map/ap-map.component';
import { ChannelConflictsComponent } from './components/channel-conflicts/channel-conflicts.component';
import { SecurityEventsComponent } from './components/security-events/security-events.component';
import { TrendsComponent } from './components/trends/trends.component';
import { ApLifecycleComponent } from './components/ap-lifecycle/ap-lifecycle.component';
import { AdvisorComponent } from './components/advisor/advisor.component';
import { LoginComponent } from './components/login/login.component';
import { AdminComponent } from './components/admin/admin.component';
import { SettingsComponent } from './components/settings/settings.component';
import { SitesComponent } from './components/sites/sites.component';
import { ProfileComponent } from './components/profile/profile.component';
import { ReportsComponent } from './components/reports/reports.component';
import { LicensingComponent } from './components/licensing/licensing.component';
import { authGuard, adminGuard } from './guards/auth.guard';
import { licenseGuard } from './guards/license.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  // Reachable while unlicensed (authGuard only) so an admin can activate.
  { path: 'licensing', component: LicensingComponent, canActivate: [authGuard] },
  { path: '', redirectTo: 'overview', pathMatch: 'full' },
  { path: 'overview', component: OverviewComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'access-points', component: ApListComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'map', component: ApMapComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'clients', component: ClientListComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'client-experience', component: ClientExperienceComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'wlans', component: WlanListComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'rf-conflicts', component: ChannelConflictsComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'lifecycle', component: ApLifecycleComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'advisor', component: AdvisorComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'system', component: SystemInfoComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'roaming-graph', component: RoamingGraphComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'tracking', component: ClientTrackingComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'trends', component: TrendsComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'events', component: SecurityEventsComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'reports', component: ReportsComponent, canActivate: [authGuard, licenseGuard] },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'admin', component: AdminComponent, canActivate: [adminGuard, licenseGuard] },
  { path: 'sites', component: SitesComponent, canActivate: [adminGuard, licenseGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [adminGuard, licenseGuard] },
  { path: '**', redirectTo: 'overview' },
];
