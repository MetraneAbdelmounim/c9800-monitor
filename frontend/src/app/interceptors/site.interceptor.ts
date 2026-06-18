import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { SiteContextService } from '../services/site-context.service';

// Endpoints that are global (not per-site) — never get a ?site= param.
const EXCLUDE = ['/api/auth', '/api/license', '/api/sites', '/api/overview'];

/**
 * Appends ?site=<currentSiteId> to GET /api/* requests so each view is scoped
 * to the selected site. Global/config endpoints are excluded.
 */
export const siteInterceptor: HttpInterceptorFn = (req, next) => {
  const ctx = inject(SiteContextService);
  const id = ctx.currentId();
  const isApiGet = req.method === 'GET' && req.url.includes('/api/');
  const excluded = EXCLUDE.some(p => req.url.includes(p));

  if (id && isApiGet && !excluded && !req.params.has('site')) {
    return next(req.clone({ params: req.params.set('site', id) }));
  }
  return next(req);
};
