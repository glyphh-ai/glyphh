import { staffAnswers, staffMe } from './adminData';
import { gamesHandlers } from './games';
import { http, HttpResponse, v1 } from './server';

export * from './adminData';

/** The fake server as it answers a staff member: `server.use(...staffHandlers())`. */
export const staffHandlers = () => [
  http.get(v1('/me'), () => HttpResponse.json(staffMe)),
  ...gamesHandlers(),
  ...Object.entries(staffAnswers).map(([path, answer]) => http.get(v1(path), () => HttpResponse.json(answer))),
];
