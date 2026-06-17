from app.redis_client import r
class UserCacheService:
    TTL = 600

    @staticmethod
    async def get(user_id:int):
        ans =  await r.hgetall(f"user:{user_id}")
        # print("Ans",ans)
        return ans
    
    @staticmethod
    async def save(user):
        await r.hset(f"user:{user.id}",
                    mapping={
                        "id":str(user.id),
                        "username":user.username,
                        "role":user.role.value
                    }
                    )
        await r.expire(f"user:{user.id}",UserCacheService.TTL)

    @staticmethod
    async def delete(user_id:int):
        await r.delete(f"user:{user_id}")
        
