import { getUserByIdRefresh } from '@/lib/db/user';
import { RequestAuthedUser, withAuthedUser } from '@/lib/with-user';
import { NextResponse } from 'next/server';

export const POST = withAuthedUser(async (request: RequestAuthedUser) => {
  const user = await getUserByIdRefresh(request.user.id);

  return NextResponse.json(user);
});
