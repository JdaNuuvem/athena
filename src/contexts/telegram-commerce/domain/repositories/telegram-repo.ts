import type { ChatOrder, ChatSession } from '../entities'
export interface IChatOrderRepository { save(o: ChatOrder): Promise<void>; findById(id: string): Promise<ChatOrder | null>; findByUser(userId: string): Promise<ChatOrder[]> }
export interface IChatSessionRepository { save(s: ChatSession): Promise<void>; findByUser(userId: string): Promise<ChatSession | null> }
