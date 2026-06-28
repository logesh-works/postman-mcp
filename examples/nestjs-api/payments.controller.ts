// Minimal NestJS payments controller: OpenAPI path via @nestjs/swagger.
//
// Postman MCP reads the @Controller/@Post decorators, the DTO (class-validator), and the
// @UseGuards auth guard. With @nestjs/swagger configured, the generated spec (/api-json)
// is the high-confidence input path.
//
// Scaffold: module/bootstrap wiring is omitted; see the NestJS docs.

import { Body, Controller, Get, Param, Post, UseGuards } from "@nestjs/common";
import { ApiProperty } from "@nestjs/swagger";
import { IsInt, IsString, Min } from "class-validator";

class CreatePaymentDto {
  @ApiProperty({ type: Number, example: 4200 })
  @IsInt()
  @Min(1)
  amount: number; // Amount in minor units (cents)

  @ApiProperty({ type: String, default: "USD" })
  @IsString()
  currency: string = "USD"; // ISO 4217 code

  @ApiProperty({ type: String, enum: ["card", "bank", "wallet"] })
  @IsString()
  method: string; // card | bank | wallet
}

// Stand-in for your real auth guard → Bearer {{token}}
class AuthGuard {}

@Controller("payments")
@UseGuards(AuthGuard)
export class PaymentsController {
  /** Create a new payment. */
  @Post()
  create(@Body() body: CreatePaymentDto) {
    return {
      id: "pay_abc123",
      amount: body.amount,
      currency: body.currency,
      status: "succeeded",
      created_at: "2026-06-27T10:00:00Z",
    };
  }

  /** Fetch a single payment by id. */
  @Get(":id")
  findOne(@Param("id") id: string) {
    return { id, amount: 4200, currency: "USD", status: "succeeded" };
  }
}
