import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.getToken();

  const authed = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authed).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !req.url.endsWith('/auth/login')) {
        auth.logout();
        router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
      } else if (err.status === 402 && !req.url.endsWith('/license') && !auth.mustChangePassword()) {
        // App is locked (no valid license) — send the user to activation, UNLESS a
        // forced password change is still pending (that flow takes precedence).
        router.navigate(['/licensing']);
      }
      return throwError(() => err);
    })
  );
};
