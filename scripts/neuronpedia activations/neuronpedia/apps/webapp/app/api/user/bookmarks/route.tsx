import { getBookmarksByUser } from '@/lib/db/bookmark';
import { RequestAuthedUser, withAuthedUser } from '@/lib/with-user';
import { NextResponse } from 'next/server';

export const POST = withAuthedUser(async (request: RequestAuthedUser) => {
  const bookmarks = await getBookmarksByUser(request.user);
  return NextResponse.json(bookmarks);
});
