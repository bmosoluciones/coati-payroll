/*
 * SPDX-License-Identifier: Apache-2.0
 * SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
 *
 * Service Worker for Coati Payroll PWA.
 *
 * This service worker does not provide offline caching of application data.
 * Its sole purpose is to intercept failed navigation requests (caused by
 * network loss) and display a friendly "check your internet connection" page.
 */

const OFFLINE_URL = './offline.html';

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open('coati-pwa-v1').then(function (cache) {
            return cache.add(OFFLINE_URL);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function (event) {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(function () {
                return caches.match(OFFLINE_URL);
            })
        );
    }
});
