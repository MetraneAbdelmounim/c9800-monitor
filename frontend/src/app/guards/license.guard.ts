import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map, catchError, of } from 'rxjs';
import { LicenseService } from '../services/license.service';

/**
 * Blocks protected routes until a valid license is active. Runs after authGuard,
 * so the user is already authenticated here. Redirects to /licensing otherwise.
 */
export const licenseGuard: CanActivateFn = () => {
  const lic = inject(LicenseService);
  const router = inject(Router);

  if (lic.isValid()) return true;

  return lic.status().pipe(
    map(info => (info.valid ? true : router.createUrlTree(['/licensing']))),
    catchError(() => of(router.createUrlTree(['/licensing']))),
  );
};