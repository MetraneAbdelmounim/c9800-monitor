import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withHashLocation } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './interceptors/auth.interceptor';
import { siteInterceptor } from './interceptors/site.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    // Hash routing (#/dashboard …) so the SPA needs no server-side rewrite
    // rules — the backend only ever serves index.html + static assets.
    provideRouter(routes, withHashLocation()),
    provideHttpClient(withInterceptors([authInterceptor, siteInterceptor])),
  ]
};
