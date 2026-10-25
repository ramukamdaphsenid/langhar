import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { LocationStrategy, PathLocationStrategy } from '@angular/common';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { appRoutes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withFetch()),
    { provide: LocationStrategy, useClass: PathLocationStrategy },
    provideRouter(appRoutes)
  ]
};
