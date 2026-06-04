import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Block navigation if the user still owes a password change. */
function passwordGate(auth: AuthService, router: Router, targetUrl: string) {
  if (auth.mustChangePassword() && !targetUrl.startsWith('/profile')) {
    return router.createUrlTree(['/profile'], { queryParams: { forced: 1 } });
  }
  return null;
}

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  }
  const gate = passwordGate(auth, router, state.url);
  return gate ?? true;
};

export const adminGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  }
  const gate = passwordGate(auth, router, state.url);
  if (gate) return gate;
  if (!auth.hasRole('admin')) {
    return router.createUrlTree(['/dashboard']);
  }
  return true;
};
